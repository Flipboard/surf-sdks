package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * A lightweight reference to a feed (id, title, image), used within notifications.
 *
 * <p>Mirrors {@code SurfNotification.ReferenceFeed} / {@code SurfNotification.Feed}
 * from the backend, which share the same shape.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FeedRef(
        @JsonProperty("id") String id,
        @JsonProperty("title") String title,
        @JsonProperty("image") String image
) {
}
