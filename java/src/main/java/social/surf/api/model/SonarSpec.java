package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * A Sonar's spec: subject × surfaces × content filters × poster scope. Sent on create/update
 * and returned as stored. Null fields are omitted on the wire.
 *
 * <p>{@link Subject} parts are alternatives: a post matching any of them matches. At least
 * one of {@code query}, {@code topics} or {@code hashtags} is required; every text term of a
 * {@code query} must be at least 3 characters ({@code #hashtag} terms exempt).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public record SonarSpec(
        @JsonProperty("subject") Subject subject,
        /** bluesky | mastodon | rss | podcast | youtube | leaflet | place_stream; null = all. */
        @JsonProperty("surfaces") List<String> surfaces,
        @JsonProperty("content_filters") ContentFilters contentFilters,
        @JsonProperty("poster_scope") PosterScope posterScope
) {

    /** A spec that listens for hashtags on the given surfaces (null = all). */
    public static SonarSpec hashtags(List<String> hashtags, List<String> surfaces) {
        return new SonarSpec(new Subject(null, null, hashtags), surfaces, null, null);
    }

    /** A spec that listens for a {@code /search/posts} query on the given surfaces (null = all). */
    public static SonarSpec query(String query, List<String> surfaces) {
        return new SonarSpec(new Subject(query, null, null), surfaces, null, null);
    }

    /** A spec that listens for topics (index slugs or display names) on the given surfaces (null = all). */
    public static SonarSpec topics(List<String> topicNames, List<String> surfaces) {
        return new SonarSpec(new Subject(null, topicNames.stream().map(n -> new Topic(n, null)).toList(), null),
                surfaces, null, null);
    }

    /** WHAT to listen for; the parts are alternatives. */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Subject(
            /** The /search/posts grammar: quoted phrases, {@code &&} / {@code ||}, {@code #hashtags}. */
            @JsonProperty("query") String query,
            @JsonProperty("topics") List<Topic> topics,
            /** Bare hashtags, with or without the {@code #}. Always a list. */
            @JsonProperty("hashtags") List<String> hashtags
    ) {
    }

    /** A topic by index slug ({@code climatechange}) or display name, resolved to a slug on save. */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record Topic(
            @JsonProperty("name") String name,
            /** Reserved; the global topic threshold applies today. */
            @JsonProperty("min_score") Float minScore
    ) {
    }

    /** Refinements on the matched post itself. Bridged and spam posts are always excluded. */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record ContentFilters(
            @JsonProperty("post_types") List<String> postTypes,
            @JsonProperty("lang") List<String> lang,
            @JsonProperty("has_link") Boolean hasLink,
            @JsonProperty("domains") List<String> domains,
            @JsonProperty("exclude_nsfw") Boolean excludeNsfw,
            @JsonProperty("exclude_bots") Boolean excludeBots,
            @JsonProperty("exclude_replies") Boolean excludeReplies
    ) {
    }

    /** WHO. Only {@code anyone} is accepted today. */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record PosterScope(@JsonProperty("kind") String kind) {
        public static final PosterScope ANYONE = new PosterScope("anyone");
    }
}
