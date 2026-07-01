package social.surf.api;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for {@link DiagnosticsApi}.
 *
 * <p>These are pure unit tests (no network, no credentials): they point the client's
 * developer-portal base URL at a tiny in-process {@link HttpServer} (built into the JDK,
 * no test dependency required) and assert on the request the SDK produces — method, path
 * (both decoded and raw/escaped form), the {@code X-API-Key} header, and the request body.
 *
 * <p>Run with {@code ./gradlew test} (untagged, so it is not excluded like the
 * {@code integration}-tagged {@link SurfApiIntegrationTest}).
 */
class DiagnosticsApiTest {

    private HttpServer server;
    private SurfClient client;

    // Captured details of the most recent request the mock server received.
    private volatile String lastMethod;
    private volatile String lastDecodedPath;
    private volatile String lastRawPath;
    private volatile String lastApiKey;
    private volatile String lastBody;

    @BeforeEach
    void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/", this::handle);
        server.start();
        int port = server.getAddress().getPort();

        client = new SurfClient("surf_sk_live_k", SurfClient.DEFAULT_BASE_URL, 10)
                .setDevportalUrl("http://localhost:" + port);
    }

    @AfterEach
    void tearDown() {
        if (server != null) {
            server.stop(0);
        }
    }

    private void handle(HttpExchange exchange) throws IOException {
        lastMethod = exchange.getRequestMethod();
        lastDecodedPath = exchange.getRequestURI().getPath();
        lastRawPath = exchange.getRequestURI().getRawPath();
        lastApiKey = exchange.getRequestHeaders().getFirst("X-API-Key");

        try (InputStream in = exchange.getRequestBody()) {
            lastBody = new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }

        byte[] response = "{}".getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, response.length);
        exchange.getResponseBody().write(response);
        exchange.close();
    }

    @Test
    void diagnoseWithNullAppIdHitsDiagnoseRoot() {
        client.diagnostics.diagnose(null);
        assertEquals("GET", lastMethod);
        assertEquals("/diagnose", lastDecodedPath);
    }

    @Test
    void diagnoseWithAppIdHitsApplicationRoute() {
        client.diagnostics.diagnose("app1");
        assertEquals("GET", lastMethod);
        assertEquals("/applications/app1/diagnose", lastDecodedPath);
    }

    @Test
    void diagnoseEscapesAppIdAsSingleSegment() {
        client.diagnostics.diagnose("weird/id space");
        assertEquals("GET", lastMethod);
        // The slash and space must be percent-escaped so the id stays a single path
        // segment rather than expanding into extra segments.
        assertTrue(lastRawPath.contains("weird%2Fid%20space"),
                "raw path should carry the escaped app id, got: " + lastRawPath);
    }

    @Test
    void createBundlePostsTtlMinutes() {
        client.diagnostics.createBundle("app1", 5);
        assertEquals("POST", lastMethod);
        assertEquals("/applications/app1/debug-bundle", lastDecodedPath);
        assertNotNull(lastBody);
        assertTrue(lastBody.contains("ttl_minutes"),
                "body should contain ttl_minutes, got: " + lastBody);
        assertTrue(lastBody.contains("5"),
                "body should contain the ttl value 5, got: " + lastBody);
    }

    @Test
    void getBundleEscapesToken() {
        client.diagnostics.getBundle("dbg_a/b");
        assertEquals("GET", lastMethod);
        assertTrue(lastRawPath.contains("dbg_a%2Fb"),
                "raw path should carry the escaped token, got: " + lastRawPath);
    }

    @Test
    void revokeBundleUsesDeleteAndEscapesToken() {
        client.diagnostics.revokeBundle("dbg_a/b");
        assertEquals("DELETE", lastMethod);
        assertTrue(lastRawPath.contains("dbg_a%2Fb"),
                "raw path should carry the escaped token, got: " + lastRawPath);
    }

    @Test
    void sendsApiKeyHeader() {
        client.diagnostics.diagnose(null);
        assertEquals("surf_sk_live_k", lastApiKey);
    }

    @Test
    void defaultDevportalUrl() {
        assertEquals("https://surf.social/devportal/v1", new SurfClient("k").getDevportalUrl());
    }
}
