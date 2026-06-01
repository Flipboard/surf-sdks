package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Aggregate counters for a feed.
 *
 * <p>Mirrors {@code SurfFeedStatistics} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedStatistics(
        @JsonProperty("added_count") Long addedCount,
        @JsonProperty("added_count_home_timeline") Long addedCountHomeTimeline,
        @JsonProperty("added_count_favorites") Long addedCountFavorites,
        @JsonProperty("added_count_members") Long addedCountMembers,
        @JsonProperty("total_views") Long totalViews
) {
}
