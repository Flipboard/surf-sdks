package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

/**
 * A notification feed item.
 *
 * <p>Mirrors {@code SurfNotification} from the backend. Highlight entries remain
 * dynamic maps.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Notification(
        @JsonProperty("service") String service,
        @JsonProperty("type") String type,
        @JsonProperty("created_at") String createdAt,
        @JsonProperty("actor") Feed actor,
        @JsonProperty("reference_feed") FeedRef referenceFeed,
        @JsonProperty("reference_feed_details") Feed referenceFeedDetails,
        @JsonProperty("feed") FeedRef feed,
        @JsonProperty("feed_details") Feed feedDetails,
        @JsonProperty("message") String message,
        @JsonProperty("highlight") Boolean highlight,
        @JsonProperty("highlights") List<Map<String, Object>> highlights,
        @JsonProperty("add_delta") Integer addDelta,
        @JsonProperty("favorite_delta") Integer favoriteDelta
) {
}
