package social.surf.api;

/** 403 Forbidden — token lacks the required scope. */
public class SurfScopeError extends SurfAPIError {

    public SurfScopeError(String message, int statusCode, String errorCode, String responseBody) {
        super(message, statusCode, errorCode, responseBody);
    }
}
