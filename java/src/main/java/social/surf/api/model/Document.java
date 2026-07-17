package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * A longform document (standard.site / Leaflet), returned by {@code GET /documents/{id}}.
 *
 * <p>Exactly one of {@link #contentHtml()} or {@link #pages()} is populated depending on
 * the requested format: {@code html} (the default) renders the document to HTML, while
 * {@code blocks} returns the raw block pages.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Document(
        @JsonProperty("id") String id,
        @JsonProperty("title") String title,
        @JsonProperty("description") String description,
        @JsonProperty("published_at") String publishedAt,
        @JsonProperty("path") String path,
        @JsonProperty("cover_image_url") String coverImageUrl,
        @JsonProperty("tags") List<String> tags,
        @JsonProperty("publication_uri") String publicationUri,
        @JsonProperty("publication") Publication publication,
        @JsonProperty("author") Author author,
        @JsonProperty("comments_count") int commentsCount,
        @JsonProperty("content_html") String contentHtml,
        @JsonProperty("pages") List<Object> pages
) {

    /** The document's author (AT Protocol identity). */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Author(
            @JsonProperty("did") String did,
            @JsonProperty("handle") String handle
    ) {
    }
}
