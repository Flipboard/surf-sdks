package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * A user-created custom feed.
 *
 * <p>Mirrors {@code SurfCustomFeedTypes.SurfCustomFeedDetails} (which extends
 * {@code CustomFeedMeta}) from the backend, flattened into a single record.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record CustomFeed(
        @JsonProperty("id") String id,
        @JsonProperty("title") String title,
        @JsonProperty("description") String description,
        @JsonProperty("image") String image,
        @JsonProperty("use_tile_image") Boolean useTileImage,
        @JsonProperty("autoplay_videos") Boolean autoplayVideos,
        @JsonProperty("cover_image") String coverImage,
        @JsonProperty("title_image") String titleImage,
        @JsonProperty("favorite") Boolean favorite,
        @JsonProperty("draft") Boolean draft,
        @JsonProperty("account_uri") String accountUri,
        @JsonProperty("sort") String sort,
        @JsonProperty("layout") String layout,
        @JsonProperty("visibility") String visibility,
        @JsonProperty("version") Integer version,
        @JsonProperty("features") FeedFeatures features,
        @JsonProperty("created") Long created,
        @JsonProperty("last_modified") Long lastModified,
        @JsonProperty("locked") Boolean locked,
        @JsonProperty("bluesky_feed") String blueskyFeed,
        @JsonProperty("bluesky_feed_url") String blueskyFeedUrl,
        @JsonProperty("operators") List<FeedOperator> operators,
        @JsonProperty("stats") FeedStatistics stats,
        @JsonProperty("tags") List<String> tags,
        @JsonProperty("community") FeedCommunity community
) {
}
