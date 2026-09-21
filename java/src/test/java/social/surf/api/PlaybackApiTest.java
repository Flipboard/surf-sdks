package social.surf.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for {@link PlaybackApi}: no network, no credentials. A tiny in-process
 * {@link HttpServer} stands in for the API and records what the SDK sends.
 */
class PlaybackApiTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private HttpServer server;
    private SurfClient client;

    private final List<String[]> calls = new ArrayList<>(); // {method, rawPath, query, body}
    private final Deque<String> responses = new ArrayDeque<>();

    @BeforeEach
    void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/", this::handle);
        server.start();
        client = new SurfClient("surf_sk_live_k", "http://localhost:" + server.getAddress().getPort(), 10);
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    private void handle(HttpExchange exchange) throws IOException {
        String body;
        try (InputStream in = exchange.getRequestBody()) {
            body = new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
        calls.add(new String[] {exchange.getRequestMethod(), exchange.getRequestURI().getRawPath(),
                exchange.getRequestURI().getRawQuery(), body});
        if ("POST".equals(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(204, -1); // a report answers with no content
            exchange.close();
            return;
        }
        byte[] response = (responses.isEmpty() ? "[]" : responses.poll()).getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, response.length);
        exchange.getResponseBody().write(response);
        exchange.close();
    }

    private JsonNode bodyOf(int call) throws IOException {
        return MAPPER.readTree(calls.get(call)[3]);
    }

    @Test
    void reportSendsOnlyWhatItWasGiven() throws IOException {
        client.playback.report("p1", "surf/podcast/abc", 125_000L);

        assertEquals("POST", calls.get(0)[0]);
        assertEquals("/v1/playback", calls.get(0)[1]);
        JsonNode body = bodyOf(0);
        assertEquals("p1", body.get("post_id").asText());
        assertEquals("surf/podcast/abc", body.get("feed_surf_id").asText());
        assertEquals(125_000L, body.get("position_ms").asLong());
        // An omitted duration must be ABSENT, not 0: the server leaves a known duration
        // alone when a report omits it, and 0 would claim the episode has no length.
        assertFalse(body.has("duration_ms"));
        assertFalse(body.has("completed"));
    }

    @Test
    void reportSendsAZeroPositionBecauseZeroIsReal() throws IOException {
        client.playback.report("p1", "surf/podcast/abc", 0L);

        assertTrue(bodyOf(0).has("position_ms"));
        assertEquals(0L, bodyOf(0).get("position_ms").asLong());
    }

    @Test
    void reportSendsCompletedFalseExplicitly() throws IOException {
        // False is a statement, not an omission: it is how a client says the episode is
        // not finished. The boxed Boolean is what makes the two expressible.
        client.playback.report("p1", "surf/podcast/abc", 1L, 3_600_000L, false);

        JsonNode body = bodyOf(0);
        assertTrue(body.has("completed"));
        assertFalse(body.get("completed").asBoolean());
        assertEquals(3_600_000L, body.get("duration_ms").asLong());
    }

    @Test
    void batchWrapsItemsInOrder() throws IOException {
        client.playback.reportBatch(List.of(
                PlaybackApi.item("p1", "surf/podcast/abc", 10L),
                PlaybackApi.item("p2", "surf/podcast/abc", 20L, 30L, true)));

        assertEquals("/v1/playback/batch", calls.get(0)[1]);
        JsonNode items = bodyOf(0).get("items");
        assertEquals(2, items.size());
        assertEquals("p1", items.get(0).get("post_id").asText());
        assertFalse(items.get(0).has("completed"));
        assertTrue(items.get(1).get("completed").asBoolean());
    }

    @Test
    void batchRefusesMoreThanTheServerAccepts() {
        List<Map<String, Object>> tooMany = IntStream.range(0, 101)
                .mapToObj(i -> PlaybackApi.item("p" + i, "surf/podcast/abc", i))
                .collect(Collectors.toList());

        // Better a local failure naming the cap than a 400 after uploading 101 rows.
        assertThrows(IllegalArgumentException.class, () -> client.playback.reportBatch(tooMany));
        assertTrue(calls.isEmpty());
    }

    @Test
    void emptyBatchMakesNoCall() {
        client.playback.reportBatch(List.of());
        assertTrue(calls.isEmpty());
    }

    @Test
    void recentOmitsLimitWhenNotSet() {
        responses.add("[{\"post_id\":\"p1\",\"position_ms\":5}]");
        List<Map<String, Object>> out = client.playback.recent();

        assertEquals(1, out.size());
        assertEquals("p1", out.get(0).get("post_id"));
        assertEquals(null, calls.get(0)[2]); // no limit, so the server default applies

        client.playback.recent(10);
        assertEquals("limit=10", calls.get(1)[2]);
    }

    @Test
    void positionsRepeatsTheParam() {
        client.playback.positions(List.of("a", "b"));
        assertEquals("post_id=a&post_id=b", calls.get(0)[2]);
    }

    @Test
    void positionsWithNothingToAskMakesNoCall() {
        // A list screen with no ids should not cost a round trip, and an empty post_id
        // would be a 400 rather than an empty answer.
        assertTrue(client.playback.positions(List.of("", "  ")).isEmpty());
        assertTrue(client.playback.positions(null).isEmpty());
        assertTrue(calls.isEmpty());
    }
}
