package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * One delivery channel. Only {@code push} is delivered today; {@code slack} / {@code webhook}
 * need a {@code target} URL when they land.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public record SonarChannel(
        @JsonProperty("type") String type,
        @JsonProperty("target") String target
) {
    public static final SonarChannel PUSH = new SonarChannel("push", null);
}
