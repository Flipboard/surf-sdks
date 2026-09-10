package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/** A Sonar as returned by the API: the saved spec plus its delivery settings. Timestamps are ISO-8601. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Sonar(
        /** ULID. */
        @JsonProperty("id") String id,
        @JsonProperty("owner_id") String ownerId,
        @JsonProperty("name") String name,
        @JsonProperty("enabled") Boolean enabled,
        @JsonProperty("spec") SonarSpec spec,
        /** Only {@code instant} is accepted today. */
        @JsonProperty("cadence") String cadence,
        @JsonProperty("channels") List<SonarChannel> channels,
        @JsonProperty("daily_cap") Integer dailyCap,
        @JsonProperty("tier") String tier,
        @JsonProperty("last_delivered_at") String lastDeliveredAt,
        @JsonProperty("created") String created,
        @JsonProperty("updated") String updated
) {
}
