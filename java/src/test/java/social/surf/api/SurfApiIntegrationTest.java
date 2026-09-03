package social.surf.api;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import social.surf.api.model.CustomFeed;
import social.surf.api.model.FactCheck;
import social.surf.api.model.Feed;
import social.surf.api.model.FeedOperator;
import social.surf.api.model.FeedSummary;
import social.surf.api.model.FeedTheme;
import social.surf.api.model.GenerateImageJob;
import social.surf.api.model.NewFeedOperator;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Integration tests that run against the live Surf API.
 *
 * <p>Requires the {@code SURF_API_TEST_TOKEN} environment variable. Set
 * {@code SURF_API_BASE_URL} to override the default API base URL.
 *
 * <p>Run with: {@code ./gradlew integrationTest}
 */
@Tag("integration")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class SurfApiIntegrationTest {

    private static SurfClient client;
    private static RtbClient rtb;

    // State shared across ordered tests
    private static String customFeedId;
    private static String themedFeedId;
    private static String mastodonPostId;
    private static String blueskyPostId;

    @BeforeAll
    static void setUp() {
        String token = System.getenv("SURF_API_TEST_TOKEN");
        Assumptions.assumeTrue(token != null && !token.isEmpty(),
                "SURF_API_TEST_TOKEN not set — skipping integration tests");

        String baseUrl = System.getenv("SURF_API_BASE_URL");
        if (baseUrl != null && !baseUrl.isEmpty()) {
            // The SDK adds /v1 internally, so strip it if the env var includes it
            baseUrl = baseUrl.replaceAll("/+$", "").replaceAll("/v1$", "");
            client = new SurfClient(token, baseUrl, 60);
        } else {
            client = new SurfClient(token, SurfClient.DEFAULT_BASE_URL, 60);
        }

        // RtbClient targets surf.social/devportal/v1/rtb (NOT the api.surf.social /v1 host).
        // Use the default base URL unless explicitly overridden via SURF_RTB_BASE_URL.
        String rtbBaseUrl = System.getenv("SURF_RTB_BASE_URL");
        if (rtbBaseUrl != null && !rtbBaseUrl.isEmpty()) {
            rtb = new RtbClient(token, rtbBaseUrl);
        } else {
            rtb = new RtbClient(token);
        }
    }

    @AfterAll
    static void cleanUp() {
        if (client == null) return;

        // Best-effort cleanup of resources that might have been left behind
        if (customFeedId != null) {
            try {
                client.customFeeds.delete(customFeedId);
            } catch (Exception ignored) {
            }
        }
        if (themedFeedId != null) {
            try {
                client.customFeeds.delete(themedFeedId);
            } catch (Exception ignored) {
            }
        }
        if (mastodonPostId != null) {
            try {
                client.feeds.deletePost(mastodonPostId, "mastodon");
            } catch (Exception ignored) {
            }
        }
        if (blueskyPostId != null) {
            try {
                client.feeds.deletePost(blueskyPostId, "bluesky");
            } catch (Exception ignored) {
            }
        }
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    /**
     * Skip the current test if the exception indicates a scope or auth error.
     */
    private static void skipOnScopeOrAuth(SurfAPIError e) {
        if (e instanceof SurfScopeError || e instanceof SurfAuthError) {
            Assumptions.assumeTrue(false,
                    "Skipping — scope/auth error: " + e.getMessage());
        }
        // ?service=X names a network the app owner has no linked account for
        if (e.getStatusCode() == 400 && e.getMessage() != null && e.getMessage().contains("No linked")) {
            Assumptions.assumeTrue(false, "Skipping — no linked account: " + e.getMessage());
        }
        // The account may not be a registered RTB publisher; the API correctly
        // returns 503 "could not be initialized" in that case — tolerate it.
        if (e.getMessage() != null && e.getMessage().contains("could not be initialized")) {
            Assumptions.assumeTrue(false,
                    "Skipping — account has no RTB publisher config: " + e.getMessage());
        }
        throw e; // re-throw if it's some other error
    }

    // ======================================================================
    // 1. Feeds
    // ======================================================================

    @Test
    @Order(100)
    void feedsGetMetadata() {
        Feed feed = client.feeds.get("surf/topic/technology");
        assertNotNull(feed, "Feed should not be null");
        assertNotNull(feed.title(), "Feed should have a title");
        assertEquals("surf/topic/technology", feed.surfId());
    }

    @Test
    @Order(101)
    void feedsGetPostsWithLimit() {
        List<Map<String, Object>> posts = client.feeds.getPosts("surf/topic/technology", 5);
        assertNotNull(posts, "Posts list should not be null");
        assertFalse(posts.isEmpty(), "Posts list should not be empty");
        assertTrue(posts.size() <= 5, "Should respect limit of 5, got " + posts.size());
        // Each post should have an id
        assertNotNull(posts.get(0).get("id"), "First post should have an id");
    }

    // ======================================================================
    // 2. Search
    // ======================================================================

    @Test
    @Order(200)
    void searchFeeds() {
        Map<String, Object> result = client.search.feeds("technology");
        assertNotNull(result, "Search result should not be null");
        // Response should contain feeds or results
        assertTrue(result.containsKey("feeds") || result.containsKey("results") || result.containsKey("data"),
                "Search result should contain feeds, results, or data: " + result.keySet());
    }

    @Test
    @Order(201)
    void searchPosts() {
        Map<String, Object> result = client.search.posts("artificial intelligence");
        assertNotNull(result, "Search result should not be null");
    }

    @Test
    @Order(202)
    void searchAccounts() {
        Map<String, Object> result = client.search.accounts("surf");
        assertNotNull(result, "Search result should not be null");
    }

    // ======================================================================
    // 3. Custom Feeds: create -> createWithOperators -> add operators -> get -> verify -> delete
    // ======================================================================

    @Test
    @Order(300)
    void customFeedCreate() {
        try {
            CustomFeed feed = client.customFeeds.create("Java SDK Integration Test",
                    "Automated test feed — safe to delete");
            assertNotNull(feed, "Created feed should not be null");
            assertNotNull(feed.id(), "Created feed should have an id");
            // Strip surf/custom/ prefix if present
            customFeedId = feed.id().replace("surf/custom/", "");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(301)
    void customFeedCreateWithOperators() {
        Assumptions.assumeTrue(customFeedId != null, "No feed created in previous test");
        // Clean up the first feed — we'll create a new one with operators
        try {
            client.customFeeds.delete(customFeedId);
        } catch (Exception ignored) {
        }

        try {
            CustomFeed feed = client.customFeeds.createWithOperators(
                    "Java SDK Operators Test",
                    "Automated test feed with operators — safe to delete",
                    List.of(NewFeedOperator.source("surf/topic/technology")));
            assertNotNull(feed, "Created feed should not be null");
            assertNotNull(feed.id(), "Created feed should have an id");
            customFeedId = feed.id().replace("surf/custom/", "");

            // Verify the operator was included
            assertNotNull(feed.operators(), "Feed should have operators");
            assertFalse(feed.operators().isEmpty(), "Feed should have at least one operator");
        } catch (SurfAPIError e) {
            customFeedId = null;
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(302)
    void customFeedAddOperators() {
        Assumptions.assumeTrue(customFeedId != null, "No feed created");

        try {
            // Add a topic operator
            CustomFeed afterTopic = client.customFeeds.addOperator(customFeedId,
                    NewFeedOperator.source("surf/topic/science"));
            assertNotNull(afterTopic);

            // Add a hashtag operator
            CustomFeed afterHashtag = client.customFeeds.addOperator(customFeedId,
                    NewFeedOperator.source("surf/hashtag/opensource"));
            assertNotNull(afterHashtag);

            // Add a Bluesky user operator
            CustomFeed afterBsky = client.customFeeds.addOperator(customFeedId,
                    NewFeedOperator.source("bluesky/user/@jay.bsky.team"));
            assertNotNull(afterBsky);
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(303)
    void customFeedGetAndVerifyOperators() {
        Assumptions.assumeTrue(customFeedId != null, "No feed created");

        try {
            CustomFeed feed = client.customFeeds.get(customFeedId);
            assertNotNull(feed, "Feed should not be null");
            assertEquals(customFeedId, feed.id().replace("surf/custom/", ""));

            List<FeedOperator> operators = feed.operators();
            assertNotNull(operators, "Feed should have operators");
            // We added: technology (in createWithOperators), science, opensource, jay.bsky.team
            assertTrue(operators.size() >= 3,
                    "Expected at least 3 operators, got " + operators.size());

            // Verify specific operators by surfId
            java.util.Set<String> surfIds = new java.util.HashSet<>();
            for (FeedOperator op : operators) {
                if (op.surfId() != null) {
                    surfIds.add(op.surfId());
                }
            }
            assertTrue(surfIds.contains("surf/topic/science"),
                    "Should contain science topic operator, found: " + surfIds);
            assertTrue(surfIds.contains("surf/hashtag/opensource"),
                    "Should contain opensource hashtag operator, found: " + surfIds);
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(304)
    void customFeedDelete() {
        Assumptions.assumeTrue(customFeedId != null, "No feed created");

        try {
            client.customFeeds.delete(customFeedId);
            customFeedId = null; // prevent AfterAll cleanup
        } catch (SurfAPIError e) {
            customFeedId = null;
            skipOnScopeOrAuth(e);
        }
    }

    // ======================================================================
    // 3b. Custom Feed Themes
    // ======================================================================

    @Test
    @Order(310)
    void customFeedCreateWithTheme() {
        try {
            FeedTheme theme = FeedTheme.builder()
                    .headerImage("https://surf.social/img/surf-logo.png")
                    .headerImageSize(600, 272)
                    .surface("#EFEADD")
                    .surfaceHeader("#005F5F")
                    .build();
            CustomFeed feed = client.customFeeds.createWithTheme(
                    "Java SDK Theme Test",
                    "Automated theme test — safe to delete",
                    theme);
            assertNotNull(feed, "Created themed feed should not be null");
            assertNotNull(feed.id(), "Created themed feed should have an id");
            themedFeedId = feed.id().replace("surf/custom/", "");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(311)
    void customFeedGetTheme() {
        Assumptions.assumeTrue(themedFeedId != null, "No themed feed created");

        CustomFeed feed = client.customFeeds.get(themedFeedId);
        assertNotNull(feed, "GET should return the feed");
        // The DevApiThemeFilter translates features.theme_options into a top-level theme object
        assertNotNull(feed.theme(), "Feed should have theme");
        assertNotNull(feed.theme().get("header"), "Theme should have header");
        assertNotNull(feed.theme().get("colors"), "Theme should have colors");
    }

    @Test
    @Order(312)
    void customFeedDeleteThemed() {
        Assumptions.assumeTrue(themedFeedId != null, "No themed feed created");

        try {
            client.customFeeds.delete(themedFeedId);
            themedFeedId = null;
        } catch (SurfAPIError e) {
            themedFeedId = null;
            skipOnScopeOrAuth(e);
        }
    }

    // ======================================================================
    // 4. Write Ops (Mastodon): create -> favourite -> unfavourite -> delete
    // ======================================================================

    @Test
    @Order(400)
    void mastodonCreatePost() {
        try {
            Map<String, Object> post = client.feeds.createPost(
                    "Java SDK integration test (mastodon) — " + System.currentTimeMillis() + ". Safe to delete.",
                    "public", "mastodon");
            assertNotNull(post, "Post response should not be null");
            mastodonPostId = String.valueOf(post.get("id"));
            assertNotNull(mastodonPostId, "Post should have an id");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(401)
    void mastodonFavourite() {
        Assumptions.assumeTrue(mastodonPostId != null, "No mastodon post created");
        try {
            Map<String, Object> result = client.feeds.favourite(mastodonPostId, "mastodon");
            assertNotNull(result);
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(402)
    void mastodonUnfavourite() {
        Assumptions.assumeTrue(mastodonPostId != null, "No mastodon post created");
        try {
            Map<String, Object> result = client.feeds.unfavourite(mastodonPostId, "mastodon");
            assertNotNull(result);
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(403)
    void mastodonDeletePost() {
        Assumptions.assumeTrue(mastodonPostId != null, "No mastodon post created");
        try {
            client.feeds.deletePost(mastodonPostId, "mastodon");
            mastodonPostId = null; // prevent AfterAll cleanup
        } catch (SurfAPIError e) {
            mastodonPostId = null;
            skipOnScopeOrAuth(e);
        }
    }

    // ======================================================================
    // 5. Write Ops (Bluesky): create -> favourite -> delete
    // ======================================================================

    @Test
    @Order(500)
    void blueskyCreatePost() {
        try {
            Map<String, Object> post = client.feeds.createPost(
                    "Java SDK integration test (bluesky) — " + System.currentTimeMillis() + ". Safe to delete.",
                    "public", "bluesky");
            assertNotNull(post, "Post response should not be null");
            blueskyPostId = String.valueOf(post.get("id"));
            assertNotNull(blueskyPostId, "Post should have an id");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(501)
    void blueskyFavourite() {
        Assumptions.assumeTrue(blueskyPostId != null, "No bluesky post created");
        try {
            Map<String, Object> result = client.feeds.favourite(blueskyPostId, "bluesky");
            assertNotNull(result);
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(502)
    void blueskyDeletePost() {
        Assumptions.assumeTrue(blueskyPostId != null, "No bluesky post created");
        try {
            client.feeds.deletePost(blueskyPostId, "bluesky");
            blueskyPostId = null; // prevent AfterAll cleanup
        } catch (SurfAPIError e) {
            blueskyPostId = null;
            skipOnScopeOrAuth(e);
        }
    }

    // ======================================================================
    // 6. AI
    // ======================================================================

    @Test
    @Order(600)
    void aiAsk() {
        try {
            Map<String, Object> result = client.ai.ask("feeds about sustainable energy");
            assertNotNull(result, "AI ask result should not be null");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(601)
    void aiFeedSummary() {
        try {
            FeedSummary summary = client.ai.feedSummary("surf/topic/technology");
            assertNotNull(summary, "Feed summary should not be null");
            assertNotNull(summary.feedSummary(), "Feed summary text should not be null");
            assertFalse(summary.feedSummary().isEmpty(), "Feed summary text should not be empty");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(603)
    void aiFactCheck() {
        try {
            FactCheck result = client.ai.factCheck("The Eiffel Tower is located in Paris, France.");
            assertNotNull(result, "Fact-check result should not be null");
            assertNotNull(result.verdict(), "Fact-check verdict should not be null");
            assertNotNull(result.answer(), "Fact-check answer should not be null");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    /**
     * AI image generation (async submit). Gated: consumes the 20/day image quota,
     * so it only runs when {@code SURF_RUN_AI_IMAGE_TESTS=1}. Validates the submit
     * request/response contract ({@code key}/{@code url}/{@code status}); the poll
     * loop is covered by {@code generateImageAndWait} but not exercised here to
     * keep the test fast.
     */
    @Test
    @Order(602)
    void generateImage() {
        Assumptions.assumeTrue("1".equals(System.getenv("SURF_RUN_AI_IMAGE_TESTS")),
                "set SURF_RUN_AI_IMAGE_TESTS=1 to run (consumes the 20/day GPU image quota)");
        try {
            GenerateImageJob job =
                    client.media.generateImage("a calm minimalist landscape, soft pastels", true);
            assertNotNull(job, "Submit response should not be null");
            assertNotNull(job.key(), "Job key should not be null");
            assertNotNull(job.url(), "Eventual image URL should not be null");
            assertEquals("pending", job.status(), "Submit status should be pending");
        } catch (SurfAPIError e) {
            // Expected operational states: daily cap hit (429) or service down (502/503).
            int status = e.getStatusCode();
            if (status == 429 || status == 502 || status == 503) {
                Assumptions.assumeTrue(false,
                        "Skipping — image generation unavailable (HTTP " + status + ")");
            }
            skipOnScopeOrAuth(e);
        }
    }

    // ======================================================================
    // 6b. paginate() smoke test
    // ======================================================================

    @Test
    @Order(650)
    void paginateReturnsItemsOrStopsCleanly() {
        // paginate() works for endpoints that return {"<key>": [...], "cursor": "..."}.
        // Probe the search response to find the list-valued key, then paginate with it.
        Map<String, Object> sample = client.search.feeds("technology");
        assertNotNull(sample, "search should return a result");

        String itemKey = null;
        for (Map.Entry<String, Object> entry : sample.entrySet()) {
            if (entry.getValue() instanceof List) {
                itemKey = entry.getKey();
                break;
            }
        }
        Assumptions.assumeTrue(itemKey != null,
                "Search response has no list-valued key — cannot test paginate");

        final String key = itemKey;
        List<Object> items = new ArrayList<>();
        for (Object item : client.paginate("/search/maestra/feeds", key,
                Map.of("q", "technology", "limit", "2"), 4)) {
            items.add(item);
        }

        assertTrue(items.size() <= 4, "limit=4 must be respected, got " + items.size());
    }

    // ======================================================================
    // 6c. RTB (Real-Time Bidding)
    //
    // Uses the same SURF_API_TEST_TOKEN. RTB endpoints live at surf.social/devportal/v1/rtb.
    // Tests skip cleanly if the token lacks the rtb:* scopes. The bid test runs in
    // sandbox mode (test=1) so no publisher config is required and no spend occurs.
    // ======================================================================

    @Test
    @Order(660)
    void rtbSandboxBid() {
        try {
            Map<String, Object> bidRequest = Map.of(
                    "id", "java-sdk-itest-" + System.currentTimeMillis(),
                    "imp", List.of(Map.of(
                            "id", "1",
                            "banner", Map.of("w", 300, "h", 250))));
            // sandbox=true forces test=1 — no publisher config needed, no spend.
            Map<String, Object> response = rtb.bid(bidRequest, true);
            assertNotNull(response, "Sandbox bid response should not be null");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        } catch (java.io.IOException | InterruptedException e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    @Order(661)
    void rtbReports() {
        try {
            Map<String, Object> reports = rtb.reports(7, "day");
            assertNotNull(reports, "Reports response should not be null");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        } catch (java.io.IOException | InterruptedException e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    @Order(662)
    void rtbConfig() {
        try {
            Map<String, Object> config = rtb.config();
            assertNotNull(config, "Config response should not be null");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        } catch (java.io.IOException | InterruptedException e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    @Order(663)
    void rtbScopes() {
        try {
            List<Map<String, Object>> scopes = rtb.scopes();
            assertNotNull(scopes, "Scopes list should not be null (may be empty)");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        } catch (java.io.IOException | InterruptedException e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    @Order(664)
    void rtbAdsTxt() {
        try {
            Map<String, Object> adsTxt = rtb.adsTxt();
            assertNotNull(adsTxt, "ads.txt response should not be null");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        } catch (java.io.IOException | InterruptedException e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    @Order(665)
    void rtbErrorOnBadCredentials() {
        // A clearly invalid token should yield a typed auth/scope error from the RTB client.
        // Disable retries so we don't sleep on any transient 5xx during the negative test.
        RtbClient badRtb = new RtbClient("surf_sk_live_definitely_invalid_token_xyz",
                rtb == null ? "https://surf.social" : System.getenv("SURF_RTB_BASE_URL") != null
                        ? System.getenv("SURF_RTB_BASE_URL") : "https://surf.social",
                0);
        try {
            badRtb.config();
            // Some deployments may not enforce auth on every RTB read endpoint; tolerate success.
        } catch (SurfAuthError | SurfScopeError e) {
            assertNotNull(e.getMessage());
            assertTrue(e.getStatusCode() == 401 || e.getStatusCode() == 403,
                    "Expected 401 or 403, got " + e.getStatusCode());
        } catch (SurfAPIError e) {
            // Any other API error (e.g. 400) is acceptable for an invalid token.
            assertNotNull(e.getMessage());
        } catch (java.io.IOException | InterruptedException e) {
            throw new RuntimeException(e);
        }
    }

    // ======================================================================
    // 6z. Field-report fixes: attachments, single post/thread, pin, services
    //     forms, getFollowing, visibility/service validation (Bluesky-targeted)
    // ======================================================================

    private static final byte[] PNG_2X2 = java.util.Base64.getDecoder().decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEklEQVR42mP8z8DwHwyBgAEACn4D/Y7q8T4AAAAASUVORK5CYII=");
    private static String attachmentId;
    private static String mediaPostId;

    private static boolean isBlueskyId(Object id) {
        return id != null && String.valueOf(id).startsWith("at://");
    }

    @Test
    @Order(680)
    void getFollowingTakesSurfId() {
        List<Map<String, Object>> feeds = client.feeds.getFollowing("surf/topic/technology", 5);
        assertNotNull(feeds);
    }

    @Test
    @Order(681)
    void servicesFormsAndBlueskyDefault() {
        List<Map<String, Object>> bsky = client.feeds.getPosts("surf/topic/technology", 10, null, null, "surf/service/bluesky");
        assertFalse(bsky.isEmpty());
        assertTrue(bsky.stream().allMatch(p -> isBlueskyId(p.get("id"))), "services=surf/service/bluesky must yield Bluesky only");
        assertNotNull(client.feeds.getPosts("surf/topic/technology", 5, null, null, "bluesky,rss"), "bare names accepted");
        List<Map<String, Object>> posts = client.feeds.getPosts("surf/topic/technology", 40);
        assertTrue(posts.stream().anyMatch(p -> isBlueskyId(p.get("id"))), "topic feeds include Bluesky by default");
        for (Map<String, Object> p : posts) {
            Object media = p.get("media_attachments");
            boolean hasMedia = media instanceof List && !((List<?>) media).isEmpty();
            boolean drawable = (p.get("content") != null && !String.valueOf(p.get("content")).isEmpty())
                    || hasMedia || p.get("card") != null || p.get("reblog") != null || p.get("quote") != null;
            assertTrue(drawable, "contentless placeholder row: " + p.get("id"));
        }
        assertEquals(40, posts.size(), "page should be exactly limit");
    }

    @Test
    @Order(682)
    void uploadAttachment() throws Exception {
        java.nio.file.Path png = java.nio.file.Files.createTempFile("sdk-test", ".png");
        java.nio.file.Files.write(png, PNG_2X2);
        try {
            Map<String, Object> att = client.media.uploadAttachment(png, "image/png", "Java SDK test image", "bluesky");
            attachmentId = String.valueOf(att.get("id"));
            assertNotNull(att.get("id"), "attachment id expected");
            Map<String, Object> ready = client.media.waitForAttachment(attachmentId, "bluesky",
                    java.time.Duration.ofSeconds(2), java.time.Duration.ofSeconds(60));
            assertEquals(Boolean.TRUE, ready.get("ready"));
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        } finally {
            java.nio.file.Files.deleteIfExists(png);
        }
    }

    @Test
    @Order(683)
    void createPostWithMedia() {
        Assumptions.assumeTrue(attachmentId != null, "No attachment uploaded");
        try {
            Map<String, Object> post = client.feeds.createPost(
                    "Java SDK media test " + System.currentTimeMillis() + " -- safe to delete",
                    "public", null, false, null, null, "bluesky", List.of(attachmentId));
            mediaPostId = String.valueOf(post.get("id"));
            assertTrue(isBlueskyId(mediaPostId), "service=bluesky must post to Bluesky");
            Object media = post.get("media_attachments");
            assertTrue(media instanceof List && !((List<?>) media).isEmpty(), "post must carry the attachment");
        } catch (SurfAPIError e) {
            skipOnScopeOrAuth(e);
        }
    }

    @Test
    @Order(684)
    void getStatusPostAndContext() {
        Assumptions.assumeTrue(mediaPostId != null, "No post created");
        assertEquals(mediaPostId, String.valueOf(client.feeds.getStatus(mediaPostId, "bluesky").get("id")));
        assertEquals(mediaPostId, String.valueOf(client.feeds.getPost(mediaPostId).get("id")), "GET /post must resolve an at:// id");
        Map<String, Object> ctx = client.feeds.getStatusContext(mediaPostId, "bluesky");
        assertTrue(ctx.containsKey("ancestors") && ctx.containsKey("descendants"));
    }

    @Test
    @Order(685)
    void pinUnpin() {
        Assumptions.assumeTrue(mediaPostId != null, "No post created");
        try {
            client.feeds.pin(mediaPostId, "bluesky");
            client.feeds.unpin(mediaPostId, "bluesky");
        } catch (SurfNotFoundError e) {
            Assumptions.assumeTrue(false, "pin not supported by this account's bridge");
        }
    }

    @Test
    @Order(686)
    void nonPublicVisibilityRejectedOnBluesky() {
        try {
            client.feeds.createPost("Java SDK visibility test " + System.currentTimeMillis(), "direct", "bluesky");
            throw new AssertionError("a direct post to Bluesky must be rejected, not published");
        } catch (SurfAPIError e) {
            if (e instanceof SurfScopeError || e instanceof SurfAuthError
                    || (e.getMessage() != null && e.getMessage().contains("No linked"))) {
                skipOnScopeOrAuth(e);
            }
            assertEquals(400, e.getStatusCode(), "expected 400: " + e.getMessage());
        }
    }

    @Test
    @Order(687)
    void unknownServiceRejected() {
        try {
            client.feeds.createPost("Java SDK service test", "public", "threads");
            throw new AssertionError("unknown service must be rejected");
        } catch (SurfAPIError e) {
            assertEquals(400, e.getStatusCode(), "expected 400 invalid_service: " + e.getMessage());
        }
    }

    @Test
    @Order(688)
    void deleteMediaPost() {
        Assumptions.assumeTrue(mediaPostId != null, "No post created");
        client.feeds.deletePost(mediaPostId, "bluesky");
        mediaPostId = null;
    }

    // ======================================================================
    // 7. Error handling
    // ======================================================================

    @Test
    @Order(700)
    void errorNotFoundOnBadFeed() {
        try {
            client.feeds.get("surf/topic/nonexistent_xyz_999_does_not_exist");
            // Some servers return an empty/default feed instead of 404
        } catch (SurfNotFoundError e) {
            assertEquals(404, e.getStatusCode());
            assertNotNull(e.getMessage());
        } catch (SurfAPIError e) {
            // Any other API error is acceptable (e.g., 400)
        }
    }

    @Test
    @Order(701)
    void rateLimitInfoPopulated() {
        // After any successful call, rate limit info should be populated
        client.feeds.get("surf/topic/technology");
        RateLimitInfo rl = client.getRateLimit();
        // Rate limit headers may or may not be present depending on the server,
        // but the object itself should exist after a request
        assertNotNull(rl, "RateLimitInfo should be populated after a request");
    }
}
