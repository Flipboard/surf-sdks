package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Result of a media upload.
 *
 * <p>Mirrors {@code MediaController.UploadResponse} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record MediaUploadResponse(
        @JsonProperty("url") String url
) {
}
