package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * A longform publication (standard.site / Leaflet), returned by
 * {@code GET /publications/{id}} and {@code GET /search/publications}.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Publication(
        @JsonProperty("uri") String uri,
        @JsonProperty("name") String name,
        @JsonProperty("description") String description,
        @JsonProperty("icon_url") String iconUrl,
        @JsonProperty("did") String did,
        @JsonProperty("publisher_handle") String publisherHandle,
        @JsonProperty("publisher_display_name") String publisherDisplayName,
        @JsonProperty("publisher_avatar") String publisherAvatar
) {
}
