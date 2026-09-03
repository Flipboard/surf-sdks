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

    /**
     * Base URL for developer-portal endpoints (diagnostics, debug bundles). These live on a
     * different host than the {@code /v1} data API.
     */
    public static final String DEFAULT_DEVPORTAL_URL = "https://surf.social/devportal/v1";

    /** Internal path prefix — the SDK handles this automatically. */
    static final String API_PREFIX = "/v1";
    static final String USER_AGENT = "surf-api-java/1.0.0";

    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(30);

    private final String apiKey;
    private final String baseUrl;
    private String devportalUrl = DEFAULT_DEVPORTAL_URL;
    private final Duration timeout;
    private final int maxRetries;
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
    public final LongformApi longform;
    public final DiagnosticsApi diagnostics;

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
        this(apiKey, baseUrl, timeoutSeconds, 3);
    }

    /**
     * @param apiKey         API token ({@code surf_sk_live_...} or {@code surf_sk_test_...})
     * @param baseUrl        base URL (default {@value #DEFAULT_BASE_URL})
     * @param timeoutSeconds per-request timeout in seconds
     * @param maxRetries     max retry attempts on 429 or 5xx (0 to disable, default 3)
     */
    public SurfClient(String apiKey, String baseUrl, int timeoutSeconds, int maxRetries) {
        if (apiKey == null || apiKey.isEmpty()) {
            throw new IllegalArgumentException("apiKey must not be null or empty");
        }
        if (maxRetries < 0) {
            throw new IllegalArgumentException("maxRetries must be >= 0");
        }
        this.apiKey = apiKey;
        this.baseUrl = stripTrailingSlashes(baseUrl);
        this.timeout = Duration.ofSeconds(timeoutSeconds);
        this.maxRetries = maxRetries;
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
        this.longform = new LongformApi(this);
        this.diagnostics = new DiagnosticsApi(this);
    }

    /** Rate limit info from the most recent request, or null if no request has been made. */
    public RateLimitInfo getRateLimit() {
        return rateLimit;
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    /** Base URL for developer-portal endpoints (diagnostics, debug bundles). */
    public String getDevportalUrl() {
        return devportalUrl;
    }

    /**
     * Override the developer-portal base URL (default {@value #DEFAULT_DEVPORTAL_URL}), used by
     * {@link #diagnostics}. Returns this client for chaining.
     */
    public SurfClient setDevportalUrl(String devportalUrl) {
        // Treat null/blank as "use the default" — an empty base would build a
        // relative URI and HttpRequest.uri() requires an absolute one.
        this.devportalUrl = (devportalUrl == null || devportalUrl.isBlank())
                ? DEFAULT_DEVPORTAL_URL
                : stripTrailingSlashes(devportalUrl);
        return this;
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

    // --- Developer-portal helpers: hit an absolute URL (different host), bypassing API_PREFIX. ---

    String devportalUrl(String path) {
        return devportalUrl + path;
    }

    /** GET an absolute URL returning a JSON object (developer-portal host). */
    Map<String, Object> getAbsolute(String absoluteUrl) {
        return asMap(requestAbsolute("GET", absoluteUrl, null), absoluteUrl);
    }

    /** POST to an absolute URL returning a JSON object (developer-portal host). */
    Map<String, Object> postAbsolute(String absoluteUrl, Object json) {
        return asMap(requestAbsolute("POST", absoluteUrl, json), absoluteUrl);
    }

    /** DELETE an absolute URL returning a JSON object (developer-portal host). */
    Map<String, Object> deleteAbsolute(String absoluteUrl) {
        return asMap(requestAbsolute("DELETE", absoluteUrl, null), absoluteUrl);
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
    /**
     * GET that also reports the HTTP status: the returned map carries {@code ready} =
     * {@code true} for 200 and {@code false} for 206 (media still processing).
     */
    Map<String, Object> getWithStatus(String path) {
        HttpRequest req = buildRequestAbsolute("GET", url(path), null, timeout);
        HttpResponse<byte[]> resp = send(req, path);
        Map<String, Object> result = new LinkedHashMap<>();
        byte[] body = resp.body();
        if (body != null && body.length > 0) {
            try {
                result.putAll(mapper.readValue(body, new TypeReference<Map<String, Object>>() {}));
            } catch (IOException e) {
                throw new SurfAPIError("Failed to parse response from " + path + ": " + e.getMessage());
            }
        }
        result.put("ready", resp.statusCode() == 200);
        return result;
    }

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
     *
     * <p>Retry logic is intentionally not applied here (mirrors Python's {@code _request_raw}):
     * streaming responses are not idempotent to re-request mid-stream.
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

    /**
     * Build a multipart/form-data POST with a single file field named {@code file}.
     *
     * <p>Retry logic is intentionally not applied here (mirrors Python's {@code _request_raw}):
     * binary uploads are handled by callers that manage their own retry/resume strategy.
     */
    <T> T uploadMultipart(String path, byte[] fileBytes, String filename, String contentType, Class<T> type) {
        return uploadMultipart(path, fileBytes, filename, contentType, null, type);
    }

    /** Multipart upload with extra text form fields (null values skipped) before the "file" part. */
    <T> T uploadMultipart(String path, byte[] fileBytes, String filename, String contentType,
                          Map<String, String> fields, Class<T> type) {
        String boundary = "----SurfBoundary" + UUID.randomUUID().toString().replace("-", "");
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try {
            if (fields != null) {
                for (Map.Entry<String, String> f : fields.entrySet()) {
                    if (f.getValue() == null) continue;
                    String part = "--" + boundary + "\r\n"
                            + "Content-Disposition: form-data; name=\"" + f.getKey() + "\"\r\n\r\n"
                            + f.getValue() + "\r\n";
                    out.write(part.getBytes(StandardCharsets.UTF_8));
                }
            }
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
        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            HttpResponse<byte[]> resp;
            try {
                resp = httpClient.send(req, HttpResponse.BodyHandlers.ofByteArray());
            } catch (IOException e) {
                if (attempt < maxRetries) {
                    sleepSeconds(Math.min(1L << Math.min(attempt, 6), 60L));
                    continue;
                }
                throw new SurfAPIError("Request to " + path + " failed: " + e.getMessage());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new SurfAPIError("Request to " + path + " was interrupted");
            }

            // Only update from responses that carry rate-limit headers — devportal
            // (diagnostics) responses omit them and would otherwise clobber the
            // last real data-API rate limit with zeros.
            if (resp.headers().firstValue("X-RateLimit-Limit").isPresent()) {
                this.rateLimit = new RateLimitInfo(resp.headers());
            }
            int status = resp.statusCode();

            if (status == 429 && attempt < maxRetries) {
                int retryAfter = resp.headers().firstValue("Retry-After").map(s -> {
                    try { return Integer.parseInt(s); } catch (NumberFormatException ex) { return 0; }
                }).orElse(0);
                if (retryAfter <= 0) retryAfter = 1 << Math.min(attempt, 6);
                if (retryAfter > 60) retryAfter = 60;
                sleepSeconds(retryAfter);
                continue;
            }

            if (status >= 500 && attempt < maxRetries) {
                sleepSeconds(Math.min(1L << Math.min(attempt, 6), 60L));
                continue;
            }

            checkErrors(status, resp.headers(), resp.body());
            return resp;
        }
        throw new SurfAPIError("Request to " + path + " failed after " + (maxRetries + 1) + " attempts");
    }

    // --- Absolute-URL variants (developer-portal host); same auth + retry behavior. ---

    private Object requestAbsolute(String method, String absoluteUrl, Object jsonBody) {
        HttpResponse<byte[]> resp = executeAbsolute(method, absoluteUrl, jsonBody, timeout);
        if (resp.statusCode() == 204) {
            return null;
        }
        return parse(resp.body(), absoluteUrl);
    }

    private HttpResponse<byte[]> executeAbsolute(String method, String absoluteUrl,
                                                 Object jsonBody, Duration requestTimeout) {
        HttpRequest req = buildRequestAbsolute(method, absoluteUrl, jsonBody, requestTimeout);
        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            HttpResponse<byte[]> resp;
            try {
                resp = httpClient.send(req, HttpResponse.BodyHandlers.ofByteArray());
            } catch (IOException e) {
                if (attempt < maxRetries) {
                    sleepSeconds(Math.min(1L << Math.min(attempt, 6), 60L));
                    continue;
                }
                throw new SurfAPIError("Request to " + absoluteUrl + " failed: " + e.getMessage());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new SurfAPIError("Request to " + absoluteUrl + " was interrupted");
            }

            // Only update from responses that carry rate-limit headers — devportal
            // (diagnostics) responses omit them and would otherwise clobber the
            // last real data-API rate limit with zeros.
            if (resp.headers().firstValue("X-RateLimit-Limit").isPresent()) {
                this.rateLimit = new RateLimitInfo(resp.headers());
            }
            int status = resp.statusCode();

            if (status == 429 && attempt < maxRetries) {
                int retryAfter = resp.headers().firstValue("Retry-After").map(s -> {
                    try { return Integer.parseInt(s); } catch (NumberFormatException ex) { return 0; }
                }).orElse(0);
                if (retryAfter <= 0) retryAfter = 1 << Math.min(attempt, 6);
                if (retryAfter > 60) retryAfter = 60;
                sleepSeconds(retryAfter);
                continue;
            }

            if (status >= 500 && attempt < maxRetries) {
                sleepSeconds(Math.min(1L << Math.min(attempt, 6), 60L));
                continue;
            }

            checkErrors(status, resp.headers(), resp.body());
            return resp;
        }
        throw new SurfAPIError("Request to " + absoluteUrl + " failed after " + (maxRetries + 1) + " attempts");
    }

    private HttpRequest buildRequestAbsolute(String method, String absoluteUrl,
                                             Object jsonBody, Duration requestTimeout) {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(absoluteUrl))
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

    private void sleepSeconds(long seconds) {
        try {
            Thread.sleep(seconds * 1_000L);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
            throw new SurfAPIError("Request interrupted during retry backoff");
        }
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
            if (value instanceof Iterable<?> items) {
                // Repeatable query param (e.g. longform's `tags`): repeat the key per item.
                for (Object item : items) {
                    if (item != null) {
                        appendQueryParam(sb, entry.getKey(), item);
                    }
                }
            } else {
                appendQueryParam(sb, entry.getKey(), value);
            }
        }
        return sb.toString();
    }

    private static void appendQueryParam(StringBuilder sb, String key, Object value) {
        if (sb.length() > 0) {
            sb.append('&');
        }
        sb.append(URLEncoder.encode(key, StandardCharsets.UTF_8));
        sb.append('=');
        sb.append(URLEncoder.encode(String.valueOf(value), StandardCharsets.UTF_8));
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

    /**
     * Percent-encode a single URL path segment. Unlike query encoding, spaces become
     * {@code %20} (not {@code +}) and reserved characters such as {@code /} and {@code :}
     * are escaped, so an identifier containing them (e.g. a Bluesky AT-URI like
     * {@code at://did:plc:.../app.bsky.feed.post/...}) is carried as one segment rather
     * than expanding into extra path segments and missing the route.
     */
    static String encodePathSegment(String segment) {
        if (segment == null) {
            return "";
        }
        return URLEncoder.encode(segment, StandardCharsets.UTF_8).replace("+", "%20");
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
