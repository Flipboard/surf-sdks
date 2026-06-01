package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * A filter applied to a custom-feed operator.
 *
 * <p>Mirrors {@code SurfCustomFeedTypes.SurfFeedFilter} from the backend. Its
 * {@code surfId} field is a SurfId string.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedFilter(
        @JsonProperty("id") String id,
        @JsonProperty("surfId") String surfId,
        @JsonProperty("operator") Operator operator,
        @JsonProperty("created") Long created,
        @JsonProperty("last_modified") Long lastModified
) {
}
