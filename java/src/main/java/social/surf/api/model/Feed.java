package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * Feed metadata returned by {@code feeds.get(...)}.
 *
 * <p>Mirrors {@code SurfFeedTypes.SurfFeed} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Feed(
        @JsonProperty("title") String title,
        @JsonProperty("description") String description,
        @JsonProperty("type") String type,
        @JsonProperty("url") String url,
        @JsonProperty("uid") String uid,
        @JsonProperty("surf_id") String surfId,
        @JsonProperty("created_at") String createdAt,
        @JsonProperty("draft") Boolean draft,
        @JsonProperty("visibility") String visibility,
        @JsonProperty("author") Author author,
        @JsonProperty("surf_account") Account surfAccount,
        @JsonProperty("profile_links") List<ProfileLink> profileLinks,
        @JsonProperty("favorite") Boolean favorite,
        @JsonProperty("autoplay_videos") Boolean autoplayVideos,
        @JsonProperty("features") FeedFeatures features,
        @JsonProperty("stats") FeedStatistics stats,
        @JsonProperty("sources") List<FeedOperator> sources,
        @JsonProperty("tags") List<String> tags,
        @JsonProperty("feed_images") List<FeedImage> feedImages,
        @JsonProperty("summary_topics") List<SummaryTag> summaryTopics,
        @JsonProperty("summary_tags") List<SummaryTag> summaryTags,
        @JsonProperty("bluesky_feed") String blueskyFeed,
        @JsonProperty("bluesky_feed_url") String blueskyFeedUrl,
        @JsonProperty("community") FeedCommunity community,
        @JsonProperty("subdomain") String subdomain
) {
}
