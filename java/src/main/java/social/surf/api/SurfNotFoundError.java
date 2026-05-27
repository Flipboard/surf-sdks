package social.surf.api;

/** 404 Not Found. */
public class SurfNotFoundError extends SurfAPIError {

    public SurfNotFoundError(String message, int statusCode, String errorCode, String responseBody) {
        super(message, statusCode, errorCode, responseBody);
    }
}
