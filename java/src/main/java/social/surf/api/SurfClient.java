package social.surf.api;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpHeaders;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.UUID;
import java.util.stream.Stream;

/**
 * Client for the Surf API.
 *
 * <p>Java 17 port of the {@code surf-api} Python SDK. Networking is handled by the
 * JDK's {@link java.net.http.HttpClient}; JSON (de)serialization uses Jackson.
 * JSON object responses are returned as {@code Map<String, Object>}, mirroring the
 * dictionaries returned by the Python SDK.
 *
 * <p>Usage:
 * <pre>{@code
 * SurfClient client = new SurfClient("surf_sk_live_your_token_here");
 *
 * // Get feed metadata
 * Map<String, Object> feed = client.feeds.get("surf/topic/technology");
 *
 * // Get posts
 * Map<String, Object> posts = client.feeds.getPosts("surf/topic/technology", 20);
 *
 * // Search
 * Map<String, Object> results = client.search.feeds("artificial intelligence");
 *
 * // AI features
 * Map<String, Object> summary = client.ai.feedSummary("surf/topic/technology");
 * Map<String, Object> answer = client.ai.ask("feeds about sustainable energy");
 * }</pre>
 *
 * <p>Errors surface as unchecked {@link SurfAPIError} subclasses.
 */
public class SurfClient {

    public static final String DEFAULT_BASE_URL = "https://api.surf.social";

    /** Internal path prefix — the SDK handles this automatically. */
    static final String API_PREFIX = "/v1";
    static final String USER_AGENT = "surf-api-java/1.0.0";

    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(30);

    private final String apiKey;
    private final String baseUrl;
    private final Duration timeout;
    private final HttpClient httpClient;
    private final ObjectMapper mapper;

    private volatile RateLimitInfo rateLimit;

    // Sub-clients
    public final FeedsApi feeds;
    public final SearchApi search;
    public final AiApi ai;
    public final AccountApi account;
    public final ContentApi content;
    public final ImagesApi images;
    public final AudioApi audio;
    public final NotificationsApi notifications;
    public final PreferencesApi preferences;
    public final CustomFeedsApi customFeeds;
    public final MediaApi media;

    /** Create a client with the default base URL and a 30-second timeout. */
    public SurfClient(String apiKey) {
        this(apiKey, DEFAULT_BASE_URL, 30);
    }

    /**
     * @param apiKey         API token ({@code surf_sk_live_...} or {@code surf_sk_test_...})
     * @param baseUrl        base URL (default {@value #DEFAULT_BASE_URL})
     * @param timeoutSeconds per-request timeout in seconds
     */
    public SurfClient(String apiKey, String baseUrl, int timeoutSeconds) {
        if (apiKey == null || apiKey.isEmpty()) {
            throw new IllegalArgumentException("apiKey must not be null or empty");
        }
        this.apiKey = apiKey;
        this.baseUrl = stripTrailingSlashes(baseUrl);
        this.timeout = Duration.ofSeconds(timeoutSeconds);
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(CONNECT_TIMEOUT)
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
        this.mapper = new ObjectMapper();
        // Omit null values when serializing request bodies, so optional fields are dropped
        // (mirrors the Python SDK's conditional body construction).
        this.mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
        // Tolerate response fields the SDK models don't declare, so partial models and
        // server-side additions don't break deserialization.
        this.mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

        this.feeds = new FeedsApi(this);
        this.search = new SearchApi(this);
        this.ai = new AiApi(this);
        this.account = new AccountApi(this);
        this.content = new ContentApi(this);
        this.images = new ImagesApi(this);
        this.audio = new AudioApi(this);
        this.notifications = new NotificationsApi(this);
        this.preferences = new PreferencesApi(this);
        this.customFeeds = new CustomFeedsApi(this);
        this.media = new MediaApi(this);
    }

    /** Rate limit info from the most recent request, or null if no request has been made. */
    public RateLimitInfo getRateLimit() {
        return rateLimit;
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    // ----------------------------------------------------------------------
    // Internal request plumbing (package-private; used by the sub-API classes)
    // ----------------------------------------------------------------------

    String url(String path) {
        return baseUrl + API_PREFIX + path;
    }

    /** GET returning a JSON object. */
    Map<String, Object> get(String path) {
        return get(path, null);
    }

    Map<String, Object> get(String path, Map<String, Object> params) {
        return asMap(request("GET", path, params, null), path);
    }

    /** POST with no body. */
    Map<String, Object> post(String path) {
        return asMap(request("POST", path, null, null), path);
    }

    Map<String, Object> post(String path, Object json) {
        return asMap(request("POST", path, null, json), path);
    }

    Map<String, Object> put(String path, Object json) {
        return asMap(request("PUT", path, null, json), path);
    }

    Map<String, Object> patch(String path, Object json) {
        return asMap(request("PATCH", path, null, json), path);
    }

    Map<String, Object> delete(String path) {
        return asMap(request("DELETE", path, null, null), path);
    }

    // --- Typed JSON helpers: deserialize directly into model classes. ---

    <T> T getAs(String path, Map<String, Object> params, Class<T> type) {
        return requestAs("GET", path, params, null, type);
    }

    <T> T postAs(String path, Object json, Class<T> type) {
        return requestAs("POST", path, null, json, type);
    }

    <T> T putAs(String path, Object json, Class<T> type) {
        return requestAs("PUT", path, null, json, type);
    }

    <T> T deleteAs(String path, Class<T> type) {
        return requestAs("DELETE", path, null, null, type);
    }

    /** GET returning a JSON array deserialized into {@code List<T>}. */
    <T> List<T> getListOf(String path, Map<String, Object> params, Class<T> elementType) {
        HttpResponse<byte[]> resp = execute("GET", path, params, null, timeout);
        byte[] body = resp.body();
        if (resp.statusCode() == 204 || body == null || body.length == 0) {
            return new ArrayList<>();
        }
        JavaType listType = mapper.getTypeFactory().constructCollectionType(List.class, elementType);
        try {
            return mapper.readValue(body, listType);
        } catch (IOException e) {
            throw new SurfAPIError("Failed to parse response from " + path + ": " + e.getMessage());
        }
    }

    /** GET returning a JSON array of objects as {@code List<Map<String, Object>>} (e.g. posts). */
    List<Map<String, Object>> getMapList(String path, Map<String, Object> params) {
        HttpResponse<byte[]> resp = execute("GET", path, params, null, timeout);
        byte[] body = resp.body();
        if (resp.statusCode() == 204 || body == null || body.length == 0) {
            return new ArrayList<>();
        }
        try {
            return mapper.readValue(body, new TypeReference<List<Map<String, Object>>>() {});
        } catch (IOException e) {
            throw new SurfAPIError("Failed to parse response from " + path + ": " + e.getMessage());
        }
    }

    private <T> T requestAs(String method, String path, Map<String, Object> params, Object json, Class<T> type) {
        HttpResponse<byte[]> resp = execute(method, path, params, json, timeout);
        byte[] body = resp.body();
        if (resp.statusCode() == 204 || body == null || body.length == 0) {
            return null;
        }
        try {
            return mapper.readValue(body, type);
        } catch (IOException e) {
            throw new SurfAPIError("Failed to parse response from " + path + ": " + e.getMessage());
        }
    }

    /** GET returning the raw response body as bytes (for binary endpoints). */
    byte[] getBytes(String path, Map<String, Object> params) {
        return execute("GET", path, params, null, timeout).body();
    }

    /** POST returning the raw response body as bytes (for binary endpoints). */
    byte[] postBytes(String path, Object json) {
        return execute("POST", path, null, json, timeout).body();
    }

    /** GET returning the raw response body decoded as UTF-8 text (for e.g. RSS XML). */
    String getText(String path, Map<String, Object> params) {
        byte[] body = execute("GET", path, params, null, timeout).body();
        return body == null ? "" : new String(body, StandardCharsets.UTF_8);
    }

    /**
     * POST that streams the response body line by line — used for Server-Sent Event
     * endpoints. The returned stream reads lazily from the connection; consume it fully
     * (or close it) to release the connection.
     */
    Stream<String> postLines(String path, Object json, int timeoutSeconds) {
        HttpRequest req = buildRequest("POST", path, null, json, Duration.ofSeconds(timeoutSeconds));
        HttpResponse<Stream<String>> resp;
        try {
            resp = httpClient.send(req, HttpResponse.BodyHandlers.ofLines());
        } catch (IOException e) {
            throw new SurfAPIError("Request to " + path + " failed: " + e.getMessage());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SurfAPIError("Request to " + path + " was interrupted");
        }
        this.rateLimit = new RateLimitInfo(resp.headers());
        int status = resp.statusCode();
        if (status < 200 || status >= 300) {
            String text = resp.body().reduce("", (a, b) -> a.isEmpty() ? b : a + "\n" + b);
            checkErrors(status, resp.headers(), text.getBytes(StandardCharsets.UTF_8));
        }
        return resp.body().filter(line -> !line.isEmpty());
    }

    /** Build a multipart/form-data POST with a single file field named {@code file}. */
    <T> T uploadMultipart(String path, byte[] fileBytes, String filename, String contentType, Class<T> type) {
        String boundary = "----SurfBoundary" + UUID.randomUUID().toString().replace("-", "");
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try {
            String head = "--" + boundary + "\r\n"
                    + "Content-Disposition: form-data; name=\"file\"; filename=\"" + filename + "\"\r\n"
                    + "Content-Type: " + contentType + "\r\n\r\n";
            out.write(head.getBytes(StandardCharsets.UTF_8));
            out.write(fileBytes);
            out.write(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new SurfAPIError("Failed to build multipart body: " + e.getMessage());
        }

        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(url(path)))
                .timeout(timeout)
                .header("X-API-Key", apiKey)
                .header("Accept", "application/json")
                .header("User-Agent", USER_AGENT)
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(out.toByteArray()))
                .build();

        HttpResponse<byte[]> resp = send(req, path);
        this.rateLimit = new RateLimitInfo(resp.headers());
        checkErrors(resp.statusCode(), resp.headers(), resp.body());
        byte[] body = resp.body();
        if (resp.statusCode() == 204 || body == null || body.length == 0) {
            return null;
        }
        try {
            return mapper.readValue(body, type);
        } catch (IOException e) {
            throw new SurfAPIError("Failed to parse response from " + path + ": " + e.getMessage());
        }
    }

    /**
     * Auto-paginate through results. Returns a lazy {@link Iterable} that walks the
     * {@code cursor}/{@code next_cursor} chain, yielding each item under {@code key}.
     *
     * @param limit maximum number of items to yield, or null/non-positive for no limit
     */
    public Iterable<Object> paginate(String path, String key, Map<String, Object> params, Integer limit) {
        Map<String, Object> base = params == null ? new LinkedHashMap<>() : new LinkedHashMap<>(params);
        return () -> new PaginatingIterator(path, key, base, limit);
    }

    // ----------------------------------------------------------------------
    // Core
    // ----------------------------------------------------------------------

    private Object request(String method, String path, Map<String, Object> params, Object jsonBody) {
        HttpResponse<byte[]> resp = execute(method, path, params, jsonBody, timeout);
        if (resp.statusCode() == 204) {
            return null;
        }
        return parse(resp.body(), path);
    }

    private HttpResponse<byte[]> execute(String method, String path, Map<String, Object> params,
                                         Object jsonBody, Duration requestTimeout) {
        HttpRequest req = buildRequest(method, path, params, jsonBody, requestTimeout);
        HttpResponse<byte[]> resp = send(req, path);
        this.rateLimit = new RateLimitInfo(resp.headers());
        checkErrors(resp.statusCode(), resp.headers(), resp.body());
        return resp;
    }

    private HttpResponse<byte[]> send(HttpRequest req, String path) {
        try {
            return httpClient.send(req, HttpResponse.BodyHandlers.ofByteArray());
        } catch (IOException e) {
            throw new SurfAPIError("Request to " + path + " failed: " + e.getMessage());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SurfAPIError("Request to " + path + " was interrupted");
        }
    }

    private HttpRequest buildRequest(String method, String path, Map<String, Object> params,
                                     Object jsonBody, Duration requestTimeout) {
        String uri = url(path);
        String query = buildQuery(params);
        if (!query.isEmpty()) {
            uri = uri + "?" + query;
        }

        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(uri))
                .timeout(requestTimeout)
                .header("X-API-Key", apiKey)
                .header("Accept", "application/json")
                .header("User-Agent", USER_AGENT);

        HttpRequest.BodyPublisher publisher;
        if (jsonBody != null) {
            byte[] body;
            try {
                body = mapper.writeValueAsBytes(jsonBody);
            } catch (IOException e) {
                throw new SurfAPIError("Failed to encode request body: " + e.getMessage());
            }
            publisher = HttpRequest.BodyPublishers.ofByteArray(body);
            builder.header("Content-Type", "application/json");
        } else {
            publisher = HttpRequest.BodyPublishers.noBody();
        }

        return builder.method(method, publisher).build();
    }

    private String buildQuery(Map<String, Object> params) {
        if (params == null || params.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, Object> entry : params.entrySet()) {
            Object value = entry.getValue();
            if (value == null) {
                continue; // mirrors Python's _clean(): drop None values
            }
            if (sb.length() > 0) {
                sb.append('&');
            }
            sb.append(URLEncoder.encode(entry.getKey(), StandardCharsets.UTF_8));
            sb.append('=');
            sb.append(URLEncoder.encode(String.valueOf(value), StandardCharsets.UTF_8));
        }
        return sb.toString();
    }

    private void checkErrors(int status, HttpHeaders headers, byte[] body) {
        if (status >= 200 && status < 300) {
            return;
        }
        String text = body == null ? "" : new String(body, StandardCharsets.UTF_8);
        Map<String, Object> parsed = tryParseObject(body);
        String msg = firstNonBlank(
                str(parsed.get("error_description")),
                str(parsed.get("error")),
                text);
        String errorCode = parsed.get("error") instanceof String ? (String) parsed.get("error") : null;

        switch (status) {
            case 401:
                throw new SurfAuthError(msg, status, errorCode, text);
            case 403:
                throw new SurfScopeError(msg, status, errorCode, text);
            case 404:
                throw new SurfNotFoundError(msg, status, errorCode, text);
            case 429:
                String retryAfter = headers.firstValue("Retry-After").orElse(null);
                throw new SurfRateLimitError(msg, retryAfter, status, errorCode, text);
            default:
                throw new SurfAPIError(msg, status, errorCode, text);
        }
    }

    private Object parse(byte[] body, String path) {
        if (body == null || body.length == 0) {
            return null;
        }
        try {
            return mapper.readValue(body, Object.class);
        } catch (IOException e) {
            throw new SurfAPIError("Failed to parse response from " + path + ": " + e.getMessage());
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> asMap(Object parsed, String path) {
        if (parsed == null) {
            return new LinkedHashMap<>(); // mirrors Python returning {} for 204
        }
        if (parsed instanceof Map) {
            return (Map<String, Object>) parsed;
        }
        // Non-object JSON (e.g. a top-level array): surface it under "data" rather than
        // throwing, so callers always receive a map.
        Map<String, Object> wrapper = new LinkedHashMap<>();
        wrapper.put("data", parsed);
        return wrapper;
    }

    private Map<String, Object> tryParseObject(byte[] body) {
        Object parsed;
        try {
            parsed = (body == null || body.length == 0) ? null : mapper.readValue(body, Object.class);
        } catch (IOException e) {
            return Collections.emptyMap();
        }
        if (parsed instanceof Map) {
            @SuppressWarnings("unchecked")
            Map<String, Object> map = (Map<String, Object>) parsed;
            return map;
        }
        return Collections.emptyMap();
    }

    // ----------------------------------------------------------------------
    // Small static helpers
    // ----------------------------------------------------------------------

    /**
     * Build an ordered map from alternating key/value arguments, e.g.
     * {@code map("surf_id", id, "limit", 20)}. Keys must be strings; values may be null
     * (null query params are dropped, null body fields are omitted on serialization).
     */
    static Map<String, Object> map(Object... kv) {
        if (kv.length % 2 != 0) {
            throw new IllegalArgumentException("map() requires an even number of arguments");
        }
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) {
            m.put((String) kv[i], kv[i + 1]);
        }
        return m;
    }

    private static String stripTrailingSlashes(String s) {
        if (s == null) {
            return DEFAULT_BASE_URL;
        }
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '/') {
            end--;
        }
        return s.substring(0, end);
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    private static String firstNonBlank(String... values) {
        for (String v : values) {
            if (v != null && !v.isEmpty()) {
                return v;
            }
        }
        return "";
    }

    /** Iterator backing {@link #paginate}. */
    private final class PaginatingIterator implements Iterator<Object> {
        private final String path;
        private final String key;
        private final Map<String, Object> params;
        private final Integer limit;

        private Iterator<Object> pageItems = Collections.emptyIterator();
        private boolean exhausted = false;
        private int fetched = 0;

        PaginatingIterator(String path, String key, Map<String, Object> params, Integer limit) {
            this.path = path;
            this.key = key;
            this.params = params;
            this.limit = limit;
        }

        @Override
        public boolean hasNext() {
            if (limit != null && limit > 0 && fetched >= limit) {
                return false;
            }
            if (pageItems.hasNext()) {
                return true;
            }
            if (exhausted) {
                return false;
            }
            advance();
            return pageItems.hasNext();
        }

        @Override
        public Object next() {
            if (!hasNext()) {
                throw new NoSuchElementException();
            }
            fetched++;
            return pageItems.next();
        }

        @SuppressWarnings("unchecked")
        private void advance() {
            Map<String, Object> data = get(path, params);
            Object raw = data.get(key);
            List<Object> items = raw instanceof List ? (List<Object>) raw : new ArrayList<>();
            if (items.isEmpty()) {
                exhausted = true;
                pageItems = Collections.emptyIterator();
                return;
            }
            pageItems = items.iterator();
            Object cursor = data.get("cursor");
            if (cursor == null) {
                cursor = data.get("next_cursor");
            }
            if (cursor == null) {
                exhausted = true;
            } else {
                params.put("cursor", cursor);
            }
        }
    }
}
