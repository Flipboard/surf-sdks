package social.surf.api;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for the {@link AudioApi} podcast intelligence methods against an
 * in-process {@link HttpServer}. No network access required.
 *
 * <p>Key behaviors under test: paths and query params for episode/guest search,
 * mentions, sponsors, and show notes; null params dropped; the sponsors
 * company-or-episode requirement; and the {@link AudioApi#episodeUrlHash(String)}
 * helper against known SHA-1 vectors.
 */
class AudioApiTest {

    private static final String EPISODE_URL = "https://cdn.example.com/podcasts/ep-142.mp3";
    private static final String FLYF_ID = "d7e340ff6462708b5519d65d3faab82ecb6c4c37";

    private HttpServer server;
    private SurfClient client;

    // Captured details of the most recent request the mock server received.
    private volatile String lastMethod;
    private volatile String lastRawPath;
    private volatile String lastRawQuery;

    /** JSON body the mock server responds with; configured per-test. */
    private volatile String responseBody = "{}";

    @BeforeEach
    void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", this::handle);
        server.start();
        client = new SurfClient("surf_sk_test_abc",
                "http://127.0.0.1:" + server.getAddress().getPort(), 10);
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    private void handle(HttpExchange exchange) throws IOException {
        lastMethod = exchange.getRequestMethod();
        lastRawPath = exchange.getRequestURI().getRawPath();
        lastRawQuery = exchange.getRequestURI().getRawQuery();
        exchange.getRequestBody().readAllBytes();

        byte[] body = responseBody.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(body);
        }
    }

    // ------------------------------------------------------------------
    // episodeUrlHash
    // ------------------------------------------------------------------

    @Test
    void episodeUrlHashMatchesKnownSha1Vectors() {
        assertEquals("a9993e364706816aba3e25717850c26c9cd0d89d", AudioApi.episodeUrlHash("abc"));
        assertEquals("da39a3ee5e6b4b0d3255bfef95601890afd80709", AudioApi.episodeUrlHash(""));
        assertEquals(40, AudioApi.episodeUrlHash(EPISODE_URL).length());
    }

    // ------------------------------------------------------------------
    // Episode search
    // ------------------------------------------------------------------

    @Test
    void searchPodcastEpisodesDefaultsToLimit20() {
        responseBody = "{\"ok\":true,\"query\":\"ai\",\"total\":0,\"results\":[]}";
        Map<String, Object> resp = client.audio.searchPodcastEpisodes("ai agents");
        assertEquals("GET", lastMethod);
        assertEquals("/v1/audio/episodes/search", lastRawPath);
        assertEquals("q=ai+agents&limit=20", lastRawQuery);
        assertEquals(true, resp.get("ok"));
    }

    @Test
    void searchPodcastEpisodesPassesFlyfIdAndLimit() {
        client.audio.searchPodcastEpisodes("ai", FLYF_ID, 5);
        assertEquals("q=ai&flyf_id=" + FLYF_ID + "&limit=5", lastRawQuery);
    }

    // ------------------------------------------------------------------
    // Guest search
    // ------------------------------------------------------------------

    @Test
    void searchPodcastGuestsPassesQueryAndLimit() {
        client.audio.searchPodcastGuests("Sam Altman", 3);
        assertEquals("/v1/audio/guests/search", lastRawPath);
        assertEquals("q=Sam+Altman&limit=3", lastRawQuery);
    }

    // ------------------------------------------------------------------
    // Mentions
    // ------------------------------------------------------------------

    @Test
    void getPodcastMentionsDropsNullFilters() {
        client.audio.getPodcastMentions("Anthropic");
        assertEquals("/v1/audio/mentions", lastRawPath);
        assertEquals("entity=Anthropic&limit=20&offset=0", lastRawQuery);
    }

    @Test
    void getPodcastMentionsPassesAllFilters() {
        client.audio.getPodcastMentions("Anthropic", "organization", FLYF_ID, 50, 100);
        assertEquals("entity=Anthropic&entity_type=organization&flyf_id=" + FLYF_ID
                + "&limit=50&offset=100", lastRawQuery);
    }

    // ------------------------------------------------------------------
    // Sponsors
    // ------------------------------------------------------------------

    @Test
    void getPodcastSponsorsByCompany() {
        client.audio.getPodcastSponsorsByCompany("Squarespace");
        assertEquals("/v1/audio/sponsors", lastRawPath);
        assertEquals("company=Squarespace&limit=20&offset=0", lastRawQuery);
    }

    @Test
    void getPodcastSponsorsForEpisode() {
        String hash = AudioApi.episodeUrlHash(EPISODE_URL);
        client.audio.getPodcastSponsorsForEpisode(hash);
        assertEquals("episode_url_hash=" + hash + "&limit=20&offset=0", lastRawQuery);
        assertFalse(lastRawQuery.contains("company="), "company omitted when null");
    }

    @Test
    void getPodcastSponsorsForEpisodeUrlHashesTheUrl() {
        client.audio.getPodcastSponsorsForEpisodeUrl(EPISODE_URL);
        assertEquals("/v1/audio/sponsors", lastRawPath);
        assertEquals("episode_url_hash=" + AudioApi.episodeUrlHash(EPISODE_URL)
                + "&limit=20&offset=0", lastRawQuery);
        assertFalse(lastRawQuery.contains("episode_url="), "raw episode_url is not sent");
    }

    @Test
    void getPodcastSponsorsForEpisodeUrlForwardsLimitAndOffset() {
        client.audio.getPodcastSponsorsForEpisodeUrl(EPISODE_URL, 50, 100);
        assertEquals("episode_url_hash=" + AudioApi.episodeUrlHash(EPISODE_URL)
                + "&limit=50&offset=100", lastRawQuery);
    }

    @Test
    void getPodcastSponsorsForEpisodeUrlRequiresUrl() {
        lastMethod = null;
        assertThrows(IllegalArgumentException.class,
                () -> client.audio.getPodcastSponsorsForEpisodeUrl(null));
        assertThrows(IllegalArgumentException.class,
                () -> client.audio.getPodcastSponsorsForEpisodeUrl("", 20, 0));
        assertNull(lastMethod, "no request should be made");
    }

    @Test
    void getPodcastSponsorsCombinesCompanyAndEpisode() {
        String hash = AudioApi.episodeUrlHash(EPISODE_URL);
        client.audio.getPodcastSponsors("Squarespace", hash, FLYF_ID, 10, 5);
        assertEquals("company=Squarespace&episode_url_hash=" + hash
                + "&flyf_id=" + FLYF_ID + "&limit=10&offset=5", lastRawQuery);
    }

    @Test
    void getPodcastSponsorsRequiresCompanyOrEpisode() {
        lastMethod = null;
        assertThrows(IllegalArgumentException.class,
                () -> client.audio.getPodcastSponsors(null, null, FLYF_ID, 20, 0));
        assertThrows(IllegalArgumentException.class,
                () -> client.audio.getPodcastSponsors("", "", null, 20, 0));
        assertNull(lastMethod, "no request should be made");
    }

    // ------------------------------------------------------------------
    // Show notes
    // ------------------------------------------------------------------

    @Test
    void getShowNotesOmitsLanguageWhenNull() {
        responseBody = "{\"status\":\"ready\"}";
        Map<String, Object> resp = client.audio.getShowNotes(EPISODE_URL);
        assertEquals("/v1/audio/transcripts/show-notes", lastRawPath);
        assertTrue(lastRawQuery.startsWith("episode_url="), lastRawQuery);
        assertFalse(lastRawQuery.contains("language="), "language omitted when null");
        assertEquals("ready", resp.get("status"));
    }

    @Test
    void getShowNotesForwardsLanguage() {
        client.audio.getShowNotes(EPISODE_URL, "es");
        assertTrue(lastRawQuery.endsWith("&language=es"), lastRawQuery);
    }

    // ------------------------------------------------------------------
    // Phase 4 — fact checks, translations, catch-up, skip-to-topic
    // ------------------------------------------------------------------

    @Test
    void getFactChecksHitsFactChecksWithEpisodeUrl() {
        responseBody = "{\"ok\":true,\"total\":1,\"summary\":{\"verified\":1}}";
        Map<String, Object> resp = client.audio.getFactChecks(EPISODE_URL);
        assertEquals("GET", lastMethod);
        assertEquals("/v1/audio/fact-checks", lastRawPath);
        assertTrue(lastRawQuery.startsWith("episode_url="), lastRawQuery);
        assertEquals(true, resp.get("ok"));
        assertEquals(1, resp.get("total"));
    }

    @Test
    void getTranslationPassesEpisodeUrlAndLanguage() {
        responseBody = "{\"ok\":true,\"language\":\"es\","
                + "\"translation\":{\"translated_transcript\":\"Bienvenidos\"}}";
        Map<String, Object> resp = client.audio.getTranslation(EPISODE_URL, "es");
        assertEquals("/v1/audio/translations", lastRawPath);
        assertTrue(lastRawQuery.endsWith("&language=es"), lastRawQuery);
        assertEquals("es", resp.get("language"));
    }

    @Test
    void getTranslationForwardsRegionalLanguageCode() {
        client.audio.getTranslation(EPISODE_URL, "pt-BR");
        assertTrue(lastRawQuery.endsWith("&language=pt-BR"), lastRawQuery);
    }

    @Test
    void getCatchUpPassesTimestamp() {
        client.audio.getCatchUp(EPISODE_URL, 1830.5);
        assertEquals("/v1/audio/catch-up", lastRawPath);
        assertTrue(lastRawQuery.endsWith("&timestamp=1830.5"), lastRawQuery);
    }

    @Test
    void getCatchUpSendsZeroTimestamp() {
        // 0 is a valid playback position and must be sent, not dropped.
        client.audio.getCatchUp(EPISODE_URL, 0);
        assertTrue(lastRawQuery.endsWith("&timestamp=0.0"), lastRawQuery);
    }

    @Test
    void skipToTopicDefaultsToLimit5() {
        client.audio.skipToTopic(EPISODE_URL, "the housing market");
        assertEquals("/v1/audio/skip-to-topic", lastRawPath);
        assertTrue(lastRawQuery.contains("&topic=the+housing+market"), lastRawQuery);
        assertTrue(lastRawQuery.endsWith("&limit=5"), lastRawQuery);
    }

    @Test
    void skipToTopicForwardsLimit() {
        client.audio.skipToTopic(EPISODE_URL, "evals", 20);
        assertTrue(lastRawQuery.endsWith("&topic=evals&limit=20"), lastRawQuery);
    }

    // ------------------------------------------------------------------
    // Popularity charts
    // ------------------------------------------------------------------

    @Test
    void getPopularShowsDefaultsToUsAllIngestedOnly() {
        responseBody = "{\"ok\":true,\"region\":\"us\",\"category\":\"all\","
                + "\"snapshot_date\":\"2026-08-31\",\"ingested_only\":true,"
                + "\"limit\":50,\"shows\":[],\"total\":0}";
        Map<String, Object> resp = client.audio.getPopularShows();
        assertEquals("GET", lastMethod);
        assertEquals("/v1/audio/popular/shows", lastRawPath);
        // date is null by default and must be dropped; ingestedOnly serialized lowercase.
        assertEquals("region=us&category=all&limit=50&ingestedOnly=true", lastRawQuery);
        assertEquals(true, resp.get("ok"));
        assertEquals("2026-08-31", resp.get("snapshot_date"));
    }

    @Test
    void getPopularShowsPassesAllParams() {
        client.audio.getPopularShows("gb", "technology", 10, false, "2026-08-30");
        assertEquals("/v1/audio/popular/shows", lastRawPath);
        assertEquals("region=gb&category=technology&limit=10&ingestedOnly=false&date=2026-08-30",
                lastRawQuery);
    }

    @Test
    void getPopularEpisodesDefaultsToLimit50() {
        responseBody = "{\"ok\":true,\"snapshot_date\":\"2026-08-31\",\"limit\":50,"
                + "\"episodes\":[],\"total\":0}";
        Map<String, Object> resp = client.audio.getPopularEpisodes();
        assertEquals("GET", lastMethod);
        assertEquals("/v1/audio/popular/episodes", lastRawPath);
        assertEquals("limit=50", lastRawQuery);
        assertEquals(true, resp.get("ok"));
    }

    @Test
    void getPopularEpisodesPassesLimitAndDate() {
        client.audio.getPopularEpisodes(5, "2026-08-30");
        assertEquals("limit=5&date=2026-08-30", lastRawQuery);
    }
}
