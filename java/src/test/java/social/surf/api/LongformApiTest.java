package social.surf.api;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import social.surf.api.model.Document;
import social.surf.api.model.Publication;
import social.surf.api.model.PublicationDocumentEntry;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for {@link LongformApi} (and {@link SearchApi#publications(String)})
 * against an in-process {@link HttpServer}. No network access required.
 *
 * <p>Key behaviors under test: AT-URIs are percent-encoded as a single path segment
 * (both {@code :} and {@code /} escaped), the optional {@code format} param is omitted
 * when null, {@code tags} is sent as a repeated query param, {@code from} offsets are
 * forwarded, and responses deserialize into the typed longform models.
 */
class LongformApiTest {

    private static final String DOC_URI = "at://did:plc:x/site.standard.document/3k2a";
    private static final String DOC_URI_ENCODED = "at%3A%2F%2Fdid%3Aplc%3Ax%2Fsite.standard.document%2F3k2a";
    private static final String PUB_URI = "at://did:plc:x/site.standard.publication/9z8y";
    private static final String PUB_URI_ENCODED = "at%3A%2F%2Fdid%3Aplc%3Ax%2Fsite.standard.publication%2F9z8y";

    private HttpServer server;
    private SurfClient client;

    // Captured details of the most recent request the mock server received.
    private volatile String lastMethod;
    private volatile String lastRawPath;
    private volatile String lastRawQuery;
    private volatile String lastApiKey;

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
        lastApiKey = exchange.getRequestHeaders().getFirst("X-API-Key");
        exchange.getRequestBody().readAllBytes();

        byte[] body = responseBody.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(body);
        }
    }

    // ------------------------------------------------------------------
    // getDocument
    // ------------------------------------------------------------------

    @Test
    void getDocumentEncodesAtUriAsSinglePathSegmentAndOmitsNullFormat() {
        responseBody = "{\"id\":\"" + DOC_URI + "\",\"title\":\"Hello Longform\","
                + "\"description\":\"An essay\",\"published_at\":\"2026-07-01T00:00:00Z\","
                + "\"path\":\"/hello-longform\",\"cover_image_url\":\"https://img.example/c.jpg\","
                + "\"tags\":[\"essays\",\"tech\"],"
                + "\"publication_uri\":\"" + PUB_URI + "\","
                + "\"publication\":{\"uri\":\"" + PUB_URI + "\",\"name\":\"My Pub\"},"
                + "\"author\":{\"did\":\"did:plc:x\",\"handle\":\"writer.example\"},"
                + "\"comments_count\":7,"
                + "\"content_html\":\"<p>hi</p>\"}";

        Document doc = client.longform.getDocument(DOC_URI);

        assertEquals("GET", lastMethod);
        // The raw AT-URI must ride as ONE percent-encoded path segment: ':' and '/'
        // both escaped, so the route is /v1/documents/{one-segment}.
        assertEquals("/v1/documents/" + DOC_URI_ENCODED, lastRawPath);
        assertNull(lastRawQuery, "format=null must be omitted entirely");
        assertEquals("surf_sk_test_abc", lastApiKey);

        assertEquals(DOC_URI, doc.id());
        assertEquals("Hello Longform", doc.title());
        assertEquals("An essay", doc.description());
        assertEquals("2026-07-01T00:00:00Z", doc.publishedAt());
        assertEquals("/hello-longform", doc.path());
        assertEquals("https://img.example/c.jpg", doc.coverImageUrl());
        assertEquals(List.of("essays", "tech"), doc.tags());
        assertEquals(PUB_URI, doc.publicationUri());
        assertNotNull(doc.publication());
        assertEquals("My Pub", doc.publication().name());
        assertNotNull(doc.author());
        assertEquals("did:plc:x", doc.author().did());
        assertEquals("writer.example", doc.author().handle());
        assertEquals(7, doc.commentsCount());
        assertEquals("<p>hi</p>", doc.contentHtml());
        assertNull(doc.pages(), "html format must not populate pages");
    }

    @Test
    void getDocumentBlocksFormatSendsFormatParamAndDeserializesPages() {
        responseBody = "{\"id\":\"" + DOC_URI + "\",\"comments_count\":0,"
                + "\"pages\":[{\"blocks\":[{\"type\":\"text\",\"text\":\"hi\"}]}]}";

        Document doc = client.longform.getDocument(DOC_URI, "blocks");

        assertEquals("/v1/documents/" + DOC_URI_ENCODED, lastRawPath);
        assertEquals("blocks", queryParam(lastRawQuery, "format"));
        assertNull(doc.contentHtml());
        assertNotNull(doc.pages());
        assertEquals(1, doc.pages().size());
    }

    // ------------------------------------------------------------------
    // getPublication
    // ------------------------------------------------------------------

    @Test
    void getPublicationEncodesAtUriAndDeserializesTypedModel() {
        responseBody = "{\"uri\":\"" + PUB_URI + "\",\"name\":\"My Pub\","
                + "\"description\":\"Essays weekly\",\"icon_url\":\"https://img.example/i.png\","
                + "\"did\":\"did:plc:x\",\"publisher_handle\":\"writer.example\","
                + "\"publisher_display_name\":\"Writer\",\"publisher_avatar\":\"https://img.example/a.png\"}";

        Publication pub = client.longform.getPublication(PUB_URI);

        assertEquals("GET", lastMethod);
        assertEquals("/v1/publications/" + PUB_URI_ENCODED, lastRawPath);
        assertNull(lastRawQuery);

        assertEquals(PUB_URI, pub.uri());
        assertEquals("My Pub", pub.name());
        assertEquals("Essays weekly", pub.description());
        assertEquals("https://img.example/i.png", pub.iconUrl());
        assertEquals("did:plc:x", pub.did());
        assertEquals("writer.example", pub.publisherHandle());
        assertEquals("Writer", pub.publisherDisplayName());
        assertEquals("https://img.example/a.png", pub.publisherAvatar());
    }

    // ------------------------------------------------------------------
    // listDocuments
    // ------------------------------------------------------------------

    @Test
    void listDocumentsSendsRepeatableTagsCountAndFrom() {
        responseBody = "[{\"uri\":\"" + DOC_URI + "\",\"title\":\"One\",\"path\":\"/one\","
                + "\"published_at\":\"2026-07-02T00:00:00Z\",\"tags\":[\"tech\"]},"
                + "{\"uri\":\"at://did:plc:x/site.standard.document/3k2b\"}]";

        List<PublicationDocumentEntry> entries =
                client.longform.listDocuments(PUB_URI, List.of("tech", "ai"), 50, 10);

        assertEquals("/v1/publications/" + PUB_URI_ENCODED + "/documents", lastRawPath);
        // `tags` must be a repeated query param, one key=value pair per tag.
        assertEquals(List.of("tech", "ai"), queryParams(lastRawQuery, "tags"));
        assertEquals("50", queryParam(lastRawQuery, "count"));
        assertEquals("10", queryParam(lastRawQuery, "from"));

        assertEquals(2, entries.size());
        assertEquals(DOC_URI, entries.get(0).uri());
        assertEquals("One", entries.get(0).title());
        assertEquals("/one", entries.get(0).path());
        assertEquals("2026-07-02T00:00:00Z", entries.get(0).publishedAt());
        assertEquals(List.of("tech"), entries.get(0).tags());
        assertNull(entries.get(1).title());
    }

    @Test
    void listDocumentsDefaultsOmitTagsAndUseCount20From0() {
        responseBody = "[]";

        List<PublicationDocumentEntry> entries = client.longform.listDocuments(PUB_URI);

        assertEquals("/v1/publications/" + PUB_URI_ENCODED + "/documents", lastRawPath);
        assertTrue(queryParams(lastRawQuery, "tags").isEmpty(), "null tags must be dropped");
        assertEquals("20", queryParam(lastRawQuery, "count"));
        assertEquals("0", queryParam(lastRawQuery, "from"));
        assertTrue(entries.isEmpty());
    }

    // ------------------------------------------------------------------
    // searchPublications (longform namespace + search namespace delegate)
    // ------------------------------------------------------------------

    @Test
    void searchPublicationsSendsQueryCountAndFromAndReturnsTypedList() {
        responseBody = "[{\"uri\":\"" + PUB_URI + "\",\"name\":\"Urbanism Weekly\"},"
                + "{\"uri\":\"at://did:plc:y/site.standard.publication/1a2b\"}]";

        List<Publication> pubs = client.longform.searchPublications("urbanism", 5, 15);

        assertEquals("/v1/search/publications", lastRawPath);
        assertEquals("urbanism", queryParam(lastRawQuery, "q"));
        assertEquals("5", queryParam(lastRawQuery, "count"));
        assertEquals("15", queryParam(lastRawQuery, "from"));

        assertEquals(2, pubs.size());
        assertEquals("Urbanism Weekly", pubs.get(0).name());
        assertEquals("at://did:plc:y/site.standard.publication/1a2b", pubs.get(1).uri());
    }

    @Test
    void searchNamespacePublicationsDelegatesToSearchPublicationsEndpoint() {
        responseBody = "[{\"uri\":\"" + PUB_URI + "\",\"name\":\"My Pub\"}]";

        List<Publication> pubs = client.search.publications("leaflet essays");

        assertEquals("GET", lastMethod);
        assertEquals("/v1/search/publications", lastRawPath);
        assertEquals("leaflet essays", queryParam(lastRawQuery, "q"));
        assertEquals("20", queryParam(lastRawQuery, "count"), "default count is 20");
        assertEquals("0", queryParam(lastRawQuery, "from"), "default from is 0");
        assertEquals(1, pubs.size());
        assertEquals("My Pub", pubs.get(0).name());
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    /** Extract a single decoded query parameter value from a raw query string. */
    private static String queryParam(String rawQuery, String name) {
        List<String> values = queryParams(rawQuery, name);
        return values.isEmpty() ? null : values.get(0);
    }

    /** Extract all decoded values of a (possibly repeated) query parameter. */
    private static List<String> queryParams(String rawQuery, String name) {
        List<String> values = new ArrayList<>();
        if (rawQuery == null) {
            return values;
        }
        for (String pair : rawQuery.split("&")) {
            int eq = pair.indexOf('=');
            String key = eq >= 0 ? pair.substring(0, eq) : pair;
            if (key.equals(name)) {
                String value = eq >= 0 ? pair.substring(eq + 1) : "";
                values.add(java.net.URLDecoder.decode(value, StandardCharsets.UTF_8));
            }
        }
        return values;
    }
}
