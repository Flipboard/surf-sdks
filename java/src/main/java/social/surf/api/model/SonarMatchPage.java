package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/** A page of matches; pass {@code nextBefore} back as {@code before} for the next page ({@code null} = no next page). */
@JsonIgnoreProperties(ignoreUnknown = true)
public record SonarMatchPage(
        @JsonProperty("matches") List<SonarMatch> matches,
        @JsonProperty("next_before") Long nextBefore
) {
}
