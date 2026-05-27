package social.surf.api;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import social.surf.api.model.CustomFeed;
import social.surf.api.model.Feed;
import social.surf.api.model.FeedSummary;
import social.surf.api.model.Notification;
import social.surf.api.model.ProfileLink;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * End-to-end tests against an in-process {@link HttpServer}. No network access required:
 * the server stubs Surf API responses so we can exercise the full client code path
 * (request building, auth headers, JSON parsing, error mapping, rate-limit capture,
 * binary bodies, and SSE streaming).
 */
class SurfClientTest {

    private HttpServer server;
    private String baseUrl;

    // Captured request details for the next handler invocation.
    private final AtomicReference<String> lastPath = new AtomicReference<>();
    private final AtomicReference<String> lastQuery = new AtomicReference<>();
    private final AtomicReference<String> lastMethod = new AtomicReference<>();
    private final AtomicReference<String> lastApiKey = new AtomicReference<>();
    private final AtomicReference<String> lastBody = new AtomicReference<>();

    /** Handler whose response is configured per-test. */
    private volatile HttpHandler handler;

    @BeforeEach
    void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            lastMethod.set(exchange.getRequestMethod());
            lastPath.set(exchange.getRequestURI().getPath());
            lastQuery.set(exchange.getRequestURI().getRawQuery());
            lastApiKey.set(exchange.getRequestHeaders().getFirst("X-API-Key"));
            lastBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            handler.handle(exchange);
        });
        server.start();
        baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    private SurfClient client() {
        return new SurfClient("surf_sk_test_abc", baseUrl, 10);
    }

    private static void respond(HttpExchange exchange, int status, String contentType,
                                Map<String, String> extraHeaders, byte[] body) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", contentType);
        if (extraHeaders != null) {
            extraHeaders.forEach((k, v) -> exchange.getResponseHeaders().set(k, v));
        }
        exchange.sendResponseHeaders(status, body.length == 0 ? -1 : body.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(body);
        }
    }

    private static void json(HttpExchange exchange, int status, String body) throws IOException {
        respond(exchange, status, "application/json", null, body.getBytes(StandardCharsets.UTF_8));
    }

    @Test
    void feedDeserializesIntoTypedModelAndSendsApiKeyAndPrefix() {
        handler = ex -> json(ex, 200, "{\"title\":\"Technology\",\"surf_id\":\"surf/topic/technology\","
                + "\"author\":{\"name\":\"Tech Bot\",\"service\":\"mastodon\"},"
                + "\"tags\":[\"tech\",\"ai\"]}");

        Feed feed = client().feeds.get("surf/topic/technology");

        assertEquals("Technology", feed.title());
        assertEquals("surf/topic/technology", feed.surfId());
        assertNotNull(feed.author());
        assertEquals("Tech Bot", feed.author().name());
        assertEquals("mastodon", feed.author().service());
        assertEquals(List.of("tech", "ai"), feed.tags());
        assertEquals("GET", lastMethod.get());
        assertEquals("/v1/feed", lastPath.get(), "client should prepend the /v1 API prefix");
        assertEquals("surf/topic/technology", queryParam(lastQuery.get(), "surf_id"));
        assertEquals("surf_sk_test_abc", lastApiKey.get());
    }

    @Test
    void unknownFeedFieldsAreIgnored() {
        handler = ex -> json(ex, 200, "{\"title\":\"X\",\"brand_new_server_field\":42,"
                + "\"author\":{\"name\":\"A\",\"some_future_field\":true}}");

        Feed feed = client().feeds.get("surf/x");
        assertEquals("X", feed.title());
        assertEquals("A", feed.author().name());
    }

    @Test
    void getPostsReturnsListOfMapsAndOmitsNullOptionalParams() {
        handler = ex -> json(ex, 200, "[{\"id\":\"1\",\"content\":\"hi\"},{\"id\":\"2\"}]");

        List<Map<String, Object>> posts = client().feeds.getPosts("surf/topic/technology", 5);

        assertEquals(2, posts.size());
        assertEquals("hi", posts.get(0).get("content"));
        String q = lastQuery.get();
        assertEquals("5", queryParam(q, "limit"));
        assertEquals("surf/topic/technology", queryParam(q, "surf_id"));
        assertTrue(q != null && !q.contains("cursor"), "null cursor should be dropped from the query");
        assertTrue(!q.contains("sort"), "null sort should be dropped from the query");
    }

    @Test
    void postSerializesBodyAndOmitsNullFields() {
        handler = ex -> json(ex, 200, "{\"id\":\"123\"}");

        client().feeds.createPost("hello world");

        assertEquals("POST", lastMethod.get());
        assertEquals("/v1/statuses", lastPath.get());
        String body = lastBody.get();
        assertTrue(body.contains("\"status\":\"hello world\""), body);
        assertTrue(body.contains("\"visibility\":\"public\""), body);
        assertTrue(!body.contains("in_reply_to_id"), "null optional fields must be omitted: " + body);
        assertTrue(!body.contains("sensitive"), "false sensitive flag must be omitted: " + body);
    }

    @Test
    void noContentReturnsEmptyMap() {
        handler = ex -> {
            try {
                respond(ex, 204, "application/json", null, new byte[0]);
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        };

        Map<String, Object> result = client().feeds.deletePost("123");
        assertTrue(result.isEmpty());
        assertEquals("DELETE", lastMethod.get());
    }

    @Test
    void rateLimitHeadersAreCaptured() {
        handler = ex -> {
            try {
                respond(ex, 200, "application/json",
                        Map.of("X-RateLimit-Limit", "60",
                               "X-RateLimit-Remaining", "59",
                               "X-RateLimit-Reset", "2026-01-01T00:01:00Z"),
                        "{}".getBytes(StandardCharsets.UTF_8));
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        };

        SurfClient client = client();
        assertNull(client.getRateLimit());
        client.account.get();

        RateLimitInfo rl = client.getRateLimit();
        assertNotNull(rl);
        assertEquals(60, rl.getLimit());
        assertEquals(59, rl.getRemaining());
        assertEquals("2026-01-01T00:01:00Z", rl.getReset());
    }

    @Test
    void notFoundMapsToTypedException() {
        handler = ex -> json(ex, 404, "{\"error\":\"not_found\",\"error_description\":\"Feed not found\"}");

        SurfNotFoundError err = assertThrows(SurfNotFoundError.class,
                () -> client().feeds.get("surf/topic/nope"));
        assertEquals(404, err.getStatusCode());
        assertEquals("not_found", err.getErrorCode());
        assertEquals("Feed not found", err.getMessage());
    }

    @Test
    void authAndScopeErrorsMapToTypedExceptions() {
        handler = ex -> json(ex, 401, "{\"error\":\"unauthorized\",\"error_description\":\"bad token\"}");
        assertThrows(SurfAuthError.class, () -> client().account.get());

        handler = ex -> json(ex, 403, "{\"error\":\"insufficient_scope\"}");
        assertThrows(SurfScopeError.class, () -> client().account.get());
    }

    @Test
    void rateLimitErrorCapturesRetryAfter() {
        handler = ex -> {
            try {
                respond(ex, 429, "application/json",
                        Map.of("Retry-After", "42"),
                        "{\"error\":\"rate_limit_exceeded\"}".getBytes(StandardCharsets.UTF_8));
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        };

        SurfRateLimitError err = assertThrows(SurfRateLimitError.class,
                () -> client().ai.ask("anything"));
        assertEquals("42", err.getRetryAfter());
        assertEquals(429, err.getStatusCode());
    }

    @Test
    void binaryEndpointReturnsRawBytes() {
        byte[] payload = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, 0x00, 0x01, 0x02};
        handler = ex -> {
            try {
                respond(ex, 200, "image/jpeg", null, payload);
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        };

        byte[] result = client().images.resize("https://example.com/p.jpg", "large");
        assertEquals("/v1/image/resize", lastPath.get());
        assertEquals("large", queryParam(lastQuery.get(), "size"));
        org.junit.jupiter.api.Assertions.assertArrayEquals(payload, result);
    }

    @Test
    void buildFeedStreamsServerSentEventLines() {
        handler = ex -> respondText(ex, 200, "event: token\ndata: hello\n\ndata: world\n");

        List<String> lines = client().ai.buildFeed("make me a feed")
                .collect(Collectors.toList());

        assertEquals("POST", lastMethod.get());
        assertEquals("/v1/ai/feed-builder", lastPath.get());
        // Blank separator lines are filtered out.
        assertEquals(List.of("event: token", "data: hello", "data: world"), lines);
    }

    @Test
    void profileLinksDeserializeIntoTypedList() {
        handler = ex -> json(ex, 200, "[{\"id\":\"1\",\"account_uri\":\"https://a.example\",\"show_icon\":true},"
                + "{\"id\":\"2\",\"account_uri\":\"https://b.example\"}]");

        List<ProfileLink> links = client().account.getLinks();

        assertEquals(2, links.size());
        assertEquals("1", links.get(0).id());
        assertEquals("https://a.example", links.get(0).accountUri());
        assertEquals(Boolean.TRUE, links.get(0).showIcon());
        assertEquals("/v1/account/links", lastPath.get());
    }

    @Test
    void feedSummaryDeserializesCamelCaseKey() {
        handler = ex -> json(ex, 200, "{\"feedSummary\":\"Lots of AI news today.\"}");

        FeedSummary summary = client().ai.feedSummary("surf/topic/technology");
        assertEquals("Lots of AI news today.", summary.feedSummary());
    }

    @Test
    void customFeedDeserializesNestedOperators() {
        handler = ex -> json(ex, 200, "{\"id\":\"cf1\",\"title\":\"AI News\",\"visibility\":\"public\","
                + "\"operators\":[{\"id\":\"op1\",\"surfId\":\"surf/topic/ai\",\"operator\":\"source\"}],"
                + "\"tags\":[\"ai\"]}");

        CustomFeed feed = client().customFeeds.get("cf1");

        assertEquals("cf1", feed.id());
        assertEquals("AI News", feed.title());
        assertEquals(1, feed.operators().size());
        assertEquals("surf/topic/ai", feed.operators().get(0).surfId());
        assertEquals(social.surf.api.model.Operator.source, feed.operators().get(0).operator());
    }

    @Test
    void customFeedUnknownOperatorFallsBackToSource() {
        handler = ex -> json(ex, 200, "{\"id\":\"cf1\",\"operators\":"
                + "[{\"id\":\"op1\",\"surfId\":\"surf/topic/ai\",\"operator\":\"totally_new_operator\"}]}");

        CustomFeed feed = client().customFeeds.get("cf1");
        assertEquals(social.surf.api.model.Operator.source, feed.operators().get(0).operator());
    }

    @Test
    void notificationsDeserializeIntoTypedList() {
        handler = ex -> json(ex, 200, "[{\"service\":\"mastodon\",\"type\":\"favourite\","
                + "\"reference_feed\":{\"id\":\"f1\",\"title\":\"My Feed\"},\"add_delta\":3}]");

        List<Notification> notifications = client().notifications.list();

        assertEquals(1, notifications.size());
        assertEquals("favourite", notifications.get(0).type());
        assertEquals("My Feed", notifications.get(0).referenceFeed().title());
        assertEquals(3, notifications.get(0).addDelta());
    }

    private static void respondText(HttpExchange ex, int status, String body) {
        try {
            respond(ex, status, "text/event-stream", null, body.getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    /** Extract a single decoded query parameter value from a raw query string. */
    private static String queryParam(String rawQuery, String name) {
        if (rawQuery == null) {
            return null;
        }
        for (String pair : rawQuery.split("&")) {
            int eq = pair.indexOf('=');
            String key = eq >= 0 ? pair.substring(0, eq) : pair;
            if (key.equals(name)) {
                String value = eq >= 0 ? pair.substring(eq + 1) : "";
                return java.net.URLDecoder.decode(value, StandardCharsets.UTF_8);
            }
        }
        return null;
    }
}
