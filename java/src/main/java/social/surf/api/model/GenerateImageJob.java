package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Result of submitting an AI image-generation job (async submit/poll).
 *
 * <p>Mirrors {@code MediaController.GenerateImageResponse} from the backend.
 * {@code status} is {@code "pending"} on submit; the image is available at
 * {@code url} once the job reaches {@code done} (poll the status endpoint).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record GenerateImageJob(
        @JsonProperty("key") String key,
        @JsonProperty("url") String url,
        @JsonProperty("status") String status
) {
}
