package social.surf.api;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import social.surf.api.model.Sonar;
import social.surf.api.model.SonarMatch;
import social.surf.api.model.SonarMatchPage;
import social.surf.api.model.SonarPreview;
import social.surf.api.model.SonarSpec;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for {@link SonarsApi}: no network, no credentials. A tiny in-process
 * {@link HttpServer} stands in for the API and records what the SDK sends — method, raw path
 * (so escaping is visible), query and body — and replays canned responses.
 */
class SonarsApiTest {

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
        if ("DELETE".equals(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(204, -1);
            exchange.close();
            return;
        }
        byte[] response = (responses.isEmpty() ? "{}" : responses.poll()).getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, response.length);
        exchange.getResponseBody().write(response);
        exchange.close();
    }

    private static final SonarSpec SPEC = SonarSpec.hashtags(List.of("#opensearch"), List.of("bluesky", "mastodon"));

    @Test
    void createPostsNameSpecAndOnlyTheDeliveryFieldsGiven() {
        client.sonars.create("OpenSearch chatter", SPEC);
        assertEquals("POST", calls.get(0)[0]);
        assertEquals("/v1/sonars", calls.get(0)[1]);
        assertEquals("{\"name\":\"OpenSearch chatter\",\"spec\":{\"subject\":{\"hashtags\":[\"#opensearch\"]},\"surfaces\":[\"bluesky\",\"mastodon\"]}}",
                calls.get(0)[3], "null delivery settings are omitted, not sent as null");

        client.sonars.create("n", SPEC, false, "instant", List.of(social.surf.api.model.SonarChannel.PUSH), 20);
        assertTrue(calls.get(1)[3].endsWith("\"enabled\":false,\"cadence\":\"instant\",\"channels\":[{\"type\":\"push\"}],\"daily_cap\":20}"),
                calls.get(1)[3]);
    }

    @Test
    void listGetAndDeletePathsWithEscapedIdsAndA204Delete() {
        responses.add("[{\"id\":\"a\"},{\"id\":\"b\"}]");
        List<Sonar> all = client.sonars.list();
        assertEquals(2, all.size());
        assertEquals("GET", calls.get(0)[0]);
        assertEquals("/v1/sonars", calls.get(0)[1]);

        client.sonars.get("01j0ksyw6tgwfs0zmhhbc42kwa");
        assertEquals("/v1/sonars/01j0ksyw6tgwfs0zmhhbc42kwa", calls.get(1)[1]);
        client.sonars.get("odd/id");
        assertEquals("/v1/sonars/odd%2Fid", calls.get(2)[1]);

        Map<String, Object> out = client.sonars.delete("abc");
        assertEquals("DELETE", calls.get(3)[0]);
        assertEquals("/v1/sonars/abc", calls.get(3)[1]);
        assertTrue(out.isEmpty(), "204 -> empty map");
    }

    @Test
    void updatePatchesOnlyTheFieldsGivenAndClearDailyCapSendsAnExplicitNull() {
        client.sonars.rename("abc", "renamed");
        assertEquals("PATCH", calls.get(0)[0]);
        assertEquals("/v1/sonars/abc", calls.get(0)[1]);
        assertEquals("{\"name\":\"renamed\"}", calls.get(0)[3]);

        client.sonars.setEnabled("abc", false);
        assertEquals("{\"enabled\":false}", calls.get(1)[3]);

        // the mapper drops null map values, so clearing must send a JSON null value explicitly
        client.sonars.clearDailyCap("abc");
        assertEquals("{\"daily_cap\":null}", calls.get(2)[3]);

        client.sonars.update("abc", SurfClient.map("daily_cap", 5, "cadence", null));
        assertEquals("{\"daily_cap\":5}", calls.get(3)[3], "a null in update() is omitted, as documented");
    }

    @Test
    void matchesPassesBeforeAndLimitAndIterateFollowsNextBefore() {
        responses.add("{\"matches\":[{\"id\":3,\"sonar_id\":\"abc\",\"post_id\":\"p3\",\"matched_at\":\"2026-09-10T00:00:00Z\",\"why\":{\"matched_by\":\"hashtag\"},\"delivered\":true},"
                + "{\"id\":2,\"sonar_id\":\"abc\",\"post_id\":\"p2\",\"delivered\":false}],\"next_before\":2}");
        responses.add("{\"matches\":[{\"id\":1,\"sonar_id\":\"abc\",\"post_id\":\"p1\",\"delivered\":false}],\"next_before\":null}");

        List<String> ids = new ArrayList<>();
        for (SonarMatch m : client.sonars.iterateMatches("abc")) {
            ids.add(m.postId());
        }
        assertEquals(List.of("p3", "p2", "p1"), ids);
        assertEquals(2, calls.size(), "two pages");
        assertEquals("/v1/sonars/abc/matches", calls.get(0)[1]);
        assertNull(calls.get(0)[2], "first page has no params");
        assertEquals("before=2", calls.get(1)[2]);

        responses.add("{\"matches\":[],\"next_before\":null}");
        SonarMatchPage page = client.sonars.matches("abc", 41L, 10);
        assertEquals("before=41&limit=10", calls.get(2)[2]);
        assertTrue(page.matches().isEmpty());
        assertNull(page.nextBefore());

        responses.add("{\"matches\":[{\"id\":9,\"post_id\":\"p9\",\"delivered\":false},{\"id\":8,\"post_id\":\"p8\",\"delivered\":false}],\"next_before\":8}");
        List<String> firstOnly = new ArrayList<>();
        for (SonarMatch m : client.sonars.iterateMatches("abc", 1)) {
            firstOnly.add(m.postId());
        }
        assertEquals(List.of("p9"), firstOnly);
        assertEquals("limit=1", calls.get(3)[2], "the limit sizes the page request");
    }

    @Test
    void previewPostsTheSpecWithDaysAsAQueryParam() {
        responses.add("{\"window_days\":7,\"total\":42,\"per_day\":[{\"day\":\"2026-09-09T00:00:00.000Z\",\"count\":42}],"
                + "\"samples\":[{\"id\":\"x\",\"service\":\"bluesky\",\"snippet\":\"and today it is iPhone Air Day\",\"matched_in\":\"transcript_digest\"},"
                + "{\"id\":\"y\",\"service\":\"mastodon\",\"snippet\":\"testing #foobar\"}]}");
        SonarPreview p = client.sonars.preview(SPEC, 7);
        assertEquals("POST", calls.get(0)[0]);
        assertEquals("/v1/sonars/preview", calls.get(0)[1]);
        assertEquals("days=7", calls.get(0)[2]);
        assertEquals("{\"subject\":{\"hashtags\":[\"#opensearch\"]},\"surfaces\":[\"bluesky\",\"mastodon\"]}", calls.get(0)[3]);
        assertEquals(7, p.windowDays());
        assertEquals(42, p.total());
        // matched_in maps from the wire name when present (a highlighted text match) and is null
        // when absent (hashtag / topic matches, and older servers that never send it)
        assertEquals("transcript_digest", p.samples().get(0).matchedIn());
        assertEquals("and today it is iPhone Air Day", p.samples().get(0).snippet());
        assertNull(p.samples().get(1).matchedIn());
        assertEquals("testing #foobar", p.samples().get(1).snippet(), "the fallback snippet is still carried");
        assertEquals(1, p.perDay().size());
        assertEquals("bluesky", p.samples().get(0).service());

        client.sonars.preview(SPEC);
        assertNull(calls.get(1)[2], "no days -> no query");
    }

    @Test
    void sonarDecodesTheWireShape() {
        responses.add("{\"id\":\"abc\",\"owner_id\":\"o\",\"name\":\"n\",\"enabled\":true,"
                + "\"spec\":{\"subject\":{\"query\":\"nvidia && \\\"earnings call\\\"\",\"topics\":[{\"name\":\"climatechange\"}]},\"surfaces\":[\"bluesky\"],"
                + "\"content_filters\":{\"lang\":[\"en\"],\"exclude_replies\":true},\"poster_scope\":{\"kind\":\"anyone\"}},"
                + "\"cadence\":\"instant\",\"channels\":[{\"type\":\"push\"}],\"daily_cap\":null,\"tier\":\"free\","
                + "\"created\":\"2026-09-10T00:00:00Z\",\"updated\":\"2026-09-10T00:00:00Z\",\"unknown_future_field\":1}");
        Sonar s = client.sonars.get("abc");
        assertEquals("abc", s.id());
        assertEquals("nvidia && \"earnings call\"", s.spec().subject().query());
        assertEquals("climatechange", s.spec().subject().topics().get(0).name());
        assertEquals(List.of("en"), s.spec().contentFilters().lang());
        assertEquals(Boolean.TRUE, s.spec().contentFilters().excludeReplies());
        assertEquals(SonarSpec.PosterScope.ANYONE, s.spec().posterScope());
        assertEquals("push", s.channels().get(0).type());
        assertNull(s.dailyCap());
        assertEquals("free", s.tier());
        assertFalse(s.spec().subject().hashtags() != null && !s.spec().subject().hashtags().isEmpty());
    }
}
