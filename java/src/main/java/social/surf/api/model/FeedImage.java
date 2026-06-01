package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * An image attached to a feed (e.g. a generated "Tile" image).
 *
 * <p>Mirrors {@code ClientTypes.FeedImage} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedImage(
        @JsonProperty("type") String type,
        @JsonProperty("flipboardImage") Image flipboardImage
) {
}
