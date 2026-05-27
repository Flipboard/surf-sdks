package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * A single image rendition (one size variant).
 *
 * <p>Mirrors {@code ClientTypes.FlipboardImageProperties} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ImageProperties(
        @JsonProperty("url") String url,
        @JsonProperty("width") Integer width,
        @JsonProperty("height") Integer height,
        @JsonProperty("hints") String hints,
        @JsonProperty("alternative") ImageProperties alternative
) {
}
