package social.surf.api;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Surf RTB (Real-Time Bidding) Client.
 *
 * <p>Uses the same {@code surf_sk_live_...} API key as {@link SurfClient} via
 * {@code X-API-Key} header, but targets RTB endpoints at {@code /devportal/v1/rtb/*}.
 * The API key must include the {@code rtb:bid} and/or {@code rtb:reports} scopes.
 *
 * <pre>{@code
 * RtbClient rtb = new RtbClient("surf_sk_live_...");
 *
 * // Sandbox mode
 * Map<String, Object> response = rtb.bid(Map.of(
 *     "id", "req-1", "test", 1,
 *     "imp", List.of(Map.of("id", "1", "banner", Map.of("w", 300, "h", 250)))
 * ), true);
 *
 * // Impression/click/win/billing fire from the tracker URLs in the bid
 * // response (bid.nurl / bid.burl and the adm trackers) -- no separate call.
 * }</pre>
 */
public class RtbClient {

    private final String apiKey;
    private final String baseUrl;
    private final int maxRetries;
    private final HttpClient http;
    private final ObjectMapper mapper = new ObjectMapper();

    /** Create a client with the default base URL and 3 retries. */
    public RtbClient(String apiKey) {
        this(apiKey, "https://surf.social");
    }

    /** Create a client with the given base URL and 3 retries. */
    public RtbClient(String apiKey, String baseUrl) {
        this(apiKey, baseUrl, 3);
    }

    /**
     * @param apiKey     API token ({@code surf_sk_live_...} or {@code surf_sk_test_...})
     * @param baseUrl    base URL (default {@code https://surf.social})
     * @param maxRetries max retry attempts on 429 or 5xx (0 to disable, default 3)
     */
    public RtbClient(String apiKey, String baseUrl, int maxRetries) {
        if (maxRetries < 0) {
            throw new IllegalArgumentException("maxRetries must be >= 0");
        }
        this.apiKey = apiKey;
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.maxRetries = maxRetries;
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();
    }

    private String url(String path) {
        return baseUrl + "/devportal/v1/rtb" + path;
    }

    private Map<String, Object> request(String method, String path, Object body, Map<String, String> params)
            throws IOException, InterruptedException {
        StringBuilder urlStr = new StringBuilder(url(path));
        if (params != null && !params.isEmpty()) {
            urlStr.append("?");
            params.forEach((k, v) -> urlStr
                    .append(URLEncoder.encode(k, StandardCharsets.UTF_8))
                    .append("=")
                    .append(URLEncoder.encode(v, StandardCharsets.UTF_8))
                    .append("&"));
            urlStr.setLength(urlStr.length() - 1);
        }

        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(urlStr.toString()))
                .header("X-API-Key", apiKey)
                .header("User-Agent", "surf-api-java/1.0.0")
                .header("Accept", "application/json")
                .timeout(Duration.ofSeconds(10));

        if ("POST".equals(method)) {
            String json = body != null ? mapper.writeValueAsString(body) : "{}";
            builder.header("Content-Type", "application/json");
            builder.POST(HttpRequest.BodyPublishers.ofString(json));
        } else {
            builder.GET();
        }

        HttpRequest req = builder.build();

        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
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

            if (status == 401) {
                throw new SurfAuthError("RTB auth failed (401). Check your API key.", 401, "unauthorized", resp.body());
            }
            if (status == 403) {
                throw new SurfScopeError("RTB forbidden (403). API key may lack required rtb:* scope.", 403, "insufficient_scope", resp.body());
            }
            if (status == 429) {
                String retryAfter = resp.headers().firstValue("Retry-After").orElse(null);
                throw new SurfRateLimitError("Rate limited (429)", retryAfter, 429, "rate_limited", resp.body());
            }
            if (status >= 400) {
                throw new SurfAPIError("HTTP " + status + ": " + resp.body(),
                        status, "rtb_error", resp.body());
            }

            String respBody = resp.body();
            if (status == 204 || respBody == null || respBody.isEmpty()) {
                return new HashMap<>();
            }
            return mapper.readValue(respBody, new TypeReference<Map<String, Object>>() {});
        }
        throw new SurfAPIError("Request to " + path + " failed after " + (maxRetries + 1) + " attempts");
    }

    private void sleepSeconds(long seconds) {
        try {
            Thread.sleep(seconds * 1_000L);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
            throw new SurfAPIError("Request interrupted during retry backoff");
        }
    }

    /** Send an OpenRTB 2.5 bid request. */
    public Map<String, Object> bid(Map<String, Object> bidRequest) throws IOException, InterruptedException {
        return bid(bidRequest, false);
    }

    /** Send an OpenRTB 2.5 bid request. Set sandbox=true for test mode. */
    public Map<String, Object> bid(Map<String, Object> bidRequest, boolean sandbox)
            throws IOException, InterruptedException {
        if (sandbox) {
            bidRequest = new HashMap<>(bidRequest);
            bidRequest.put("test", 1);
        }
        return request("POST", "/bid", bidRequest, null);
    }

    /** Get RTB performance reports. */
    public Map<String, Object> reports(int days, String granularity) throws IOException, InterruptedException {
        return request("GET", "/reports", null, Map.of("days", String.valueOf(days), "granularity", granularity));
    }

    /** Get RTB configuration and tier info. */
    public Map<String, Object> config() throws IOException, InterruptedException {
        return request("GET", "/config", null, null);
    }

    /** List available RTB scopes. */
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> scopes() throws IOException, InterruptedException {
        Map<String, Object> data = request("GET", "/scopes", null, null);
        List<Map<String, Object>> result = (List<Map<String, Object>>) data.get("scopes");
        return result != null ? result : Collections.emptyList();
    }

    /**
     * Get your personalized ads.txt entry for authorizing Surf as a seller.
     * Add the returned {@code entries} to the ads.txt at the root of each
     * domain where you display Surf ads.
     */
    public Map<String, Object> adsTxt() throws IOException, InterruptedException {
        return request("GET", "/ads-txt", null, null);
    }
}
