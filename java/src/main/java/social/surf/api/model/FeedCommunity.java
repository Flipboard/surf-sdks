package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Community metadata attached to a feed.
 *
 * <p>Mirrors {@code SurfCustomFeedTypes.SurfFeedCommunity} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedCommunity(
        @JsonProperty("id") String id,
        @JsonProperty("created") Long created,
        @JsonProperty("last_modified") Long lastModified,
        @JsonProperty("about") String about,
        @JsonProperty("image") String image
) {
}
