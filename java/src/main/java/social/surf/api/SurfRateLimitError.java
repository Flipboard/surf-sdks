package social.surf.api;

/** 429 Too Many Requests — rate limit exceeded. */
public class SurfRateLimitError extends SurfAPIError {

    /** Value of the {@code Retry-After} response header (seconds), or null if absent. */
    private final String retryAfter;

    public SurfRateLimitError(String message, String retryAfter,
                              int statusCode, String errorCode, String responseBody) {
        super(message, statusCode, errorCode, responseBody);
        this.retryAfter = retryAfter;
    }

    /** Number of seconds to wait before retrying, as reported by the server, or null. */
    public String getRetryAfter() {
        return retryAfter;
    }
}
