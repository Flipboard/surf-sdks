package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * AI-generated summary of a feed's recent posts.
 *
 * <p>Mirrors {@code FeedSummaryService.SurfFeedSummary} from the backend. Note the
 * wire key is camelCase {@code feedSummary}.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedSummary(
        @JsonProperty("feedSummary") String feedSummary
) {
}
