package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * An image with its available size variants.
 *
 * <p>Mirrors {@code ClientTypes.FlipboardImage} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Image(
        @JsonProperty("original") ImageProperties original,
        @JsonProperty("xlarge") ImageProperties xlarge,
        @JsonProperty("large") ImageProperties large,
        @JsonProperty("medium") ImageProperties medium,
        @JsonProperty("small") ImageProperties small
) {
}
