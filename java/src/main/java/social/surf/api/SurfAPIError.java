package social.surf.api;

/**
 * Base exception for Surf API errors.
 *
 * <p>Unchecked (extends {@link RuntimeException}) so callers may catch it
 * selectively, mirroring the Python SDK where every Surf error derives from
 * {@code SurfAPIError(Exception)}.
 */
public class SurfAPIError extends RuntimeException {

    /** HTTP status code, or 0 if the error did not originate from an HTTP response. */
    private final int statusCode;

    /** Machine-readable error code from the response body (the {@code error} field), or null. */
    private final String errorCode;

    /** Raw response body, when available. */
    private final String responseBody;

    public SurfAPIError(String message) {
        this(message, 0, null, null);
    }

    public SurfAPIError(String message, int statusCode, String errorCode, String responseBody) {
        super(message);
        this.statusCode = statusCode;
        this.errorCode = errorCode;
        this.responseBody = responseBody;
    }

    /** HTTP status code, or 0 if unknown. */
    public int getStatusCode() {
        return statusCode;
    }

    /** Machine-readable error code from the response body, or null. */
    public String getErrorCode() {
        return errorCode;
    }

    /** Raw response body, or null when unavailable. */
    public String getResponseBody() {
        return responseBody;
    }
}
