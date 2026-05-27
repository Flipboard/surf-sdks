package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * Feature/display toggles for a feed.
 *
 * <p>Mirrors the commonly-used subset of {@code SurfFeedFeatures} from the backend;
 * additional backend fields are ignored on deserialization.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedFeatures(
        @JsonProperty("theme") String theme,
        @JsonProperty("topic_grouped") Boolean topicGrouped,
        @JsonProperty("tag_grouped") Boolean tagGrouped,
        @JsonProperty("news_clustered") Boolean newsClustered,
        @JsonProperty("show_nsfw") Boolean showNsfw,
        @JsonProperty("show_replies") Boolean showReplies,
        @JsonProperty("show_reboosts") Boolean showReboosts,
        @JsonProperty("show_quote_posts") Boolean showQuotePosts,
        @JsonProperty("diversified") Boolean diversified,
        @JsonProperty("show_videos") Boolean showVideos,
        @JsonProperty("show_native_videos") Boolean showNativeVideos,
        @JsonProperty("show_shorts") Boolean showShorts,
        @JsonProperty("show_images") Boolean showImages,
        @JsonProperty("show_native_images") Boolean showNativeImages,
        @JsonProperty("show_articles") Boolean showArticles,
        @JsonProperty("show_comments") Boolean showComments,
        @JsonProperty("show_polls") Boolean showPolls,
        @JsonProperty("show_podcasts") Boolean showPodcasts,
        @JsonProperty("default_tab") String defaultTab,
        @JsonProperty("community_ids") List<String> communityIds,
        @JsonProperty("tabs_enabled") Boolean tabsEnabled,
        @JsonProperty("reduce_spam") Boolean reduceSpam
) {
}
