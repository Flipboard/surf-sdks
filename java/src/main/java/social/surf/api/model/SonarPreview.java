package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/** {@code sonars.preview(...)}: what a spec would have matched over the trailing window. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record SonarPreview(
        @JsonProperty("window_days") int windowDays,
        @JsonProperty("total") long total,
        @JsonProperty("per_day") List<DayCount> perDay,
        /** Up to five newest matching posts. */
        @JsonProperty("samples") List<Sample> samples
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record DayCount(
            /** ISO bucket start for the day. */
            @JsonProperty("day") String day,
            @JsonProperty("count") long count
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Sample(
            @JsonProperty("id") String id,
            @JsonProperty("service") String service,
            @JsonProperty("created_at") String createdAt,
            @JsonProperty("snippet") String snippet,
            @JsonProperty("url") String url
    ) {
    }
}
