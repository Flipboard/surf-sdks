package social.surf.api;

/** 401 Unauthorized — invalid or missing API token. */
public class SurfAuthError extends SurfAPIError {

    public SurfAuthError(String message, int statusCode, String errorCode, String responseBody) {
        super(message, statusCode, errorCode, responseBody);
    }
}
