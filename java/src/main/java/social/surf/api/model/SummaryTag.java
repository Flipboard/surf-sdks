package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * A scored topic/tag derived from a feed's content.
 *
 * <p>Mirrors {@code ClientTypes.SummaryTag} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record SummaryTag(
        @JsonProperty("id") String id,
        @JsonProperty("score") Double score
) {
}
