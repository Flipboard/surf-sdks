package social.surf.api;

import java.net.http.HttpHeaders;

/** Rate limit information parsed from response headers. */
public class RateLimitInfo {

    private final int limit;
    private final int remaining;
    private final String reset;

    RateLimitInfo(HttpHeaders headers) {
        this.limit = parseIntHeader(headers, "X-RateLimit-Limit");
        this.remaining = parseIntHeader(headers, "X-RateLimit-Remaining");
        this.reset = headers.firstValue("X-RateLimit-Reset").orElse(null);
    }

    private static int parseIntHeader(HttpHeaders headers, String name) {
        String value = headers.firstValue(name).orElse(null);
        if (value == null || value.isEmpty()) {
            return 0;
        }
        try {
            return Integer.parseInt(value.trim());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    /** Maximum number of requests allowed in the current window. */
    public int getLimit() {
        return limit;
    }

    /** Requests remaining in the current window. */
    public int getRemaining() {
        return remaining;
    }

    /** Window reset time as reported by the server (typically an ISO-8601 timestamp), or null. */
    public String getReset() {
        return reset;
    }

    @Override
    public String toString() {
        return "RateLimitInfo(remaining=" + remaining + "/" + limit + ", reset=" + reset + ")";
    }
}
