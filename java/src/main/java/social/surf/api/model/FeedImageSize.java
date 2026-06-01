package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * A simple sized image (URL plus dimensions), used for author avatars.
 *
 * <p>Mirrors {@code SurfFeedTypes.SurfFeedImage} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedImageSize(
        @JsonProperty("url") String url,
        @JsonProperty("height") Long height,
        @JsonProperty("width") Long width,
        @JsonProperty("type") String type
) {
}
