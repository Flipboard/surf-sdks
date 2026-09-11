package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

/** One ledger row from {@code sonars.matches(...)}. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record SonarMatch(
        /** The {@code before} cursor value. */
        @JsonProperty("id") long id,
        @JsonProperty("sonar_id") String sonarId,
        @JsonProperty("post_id") String postId,
        /** Canonical URL/story the post is about, when known. */
        @JsonProperty("story_key") String storyKey,
        @JsonProperty("matched_at") String matchedAt,
        /** Which clause matched, plus service / surfaces / post_version. */
        @JsonProperty("why") Map<String, Object> why,
        @JsonProperty("delivered") boolean delivered,
        @JsonProperty("delivered_at") String deliveredAt
) {
}
