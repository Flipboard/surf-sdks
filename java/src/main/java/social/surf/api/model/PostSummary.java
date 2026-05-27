package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * AI-generated summary of a Bluesky post thread.
 *
 * <p>Mirrors {@code FeedSummaryService.SurfPostSummary} from the backend. Note the
 * wire key is camelCase {@code threadSummary}.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record PostSummary(
        @JsonProperty("threadSummary") String threadSummary
) {
}
