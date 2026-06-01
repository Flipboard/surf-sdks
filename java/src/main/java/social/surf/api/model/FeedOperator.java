package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * A source/operator that contributes content to a custom feed.
 *
 * <p>Mirrors {@code SurfCustomFeedTypes.SurfFeedOperator} from the backend. Its
 * {@code surfId} field is a SurfId string.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedOperator(
        @JsonProperty("id") String id,
        @JsonProperty("surfId") String surfId,
        @JsonProperty("operator") Operator operator,
        @JsonProperty("filters") List<FeedFilter> filters,
        @JsonProperty("created") Long created,
        @JsonProperty("last_modified") Long lastModified
) {
}
