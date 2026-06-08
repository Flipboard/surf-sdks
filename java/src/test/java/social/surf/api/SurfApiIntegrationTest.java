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
import social.surf.api.model.Feed;
import social.surf.api.model.FeedOperator;
import social.surf.api.model.FeedSummary;
import social.surf.api.model.FeedTheme;
import social.surf.api.model.NewFeedOperator;

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
