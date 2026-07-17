package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * Entry in a publication's document listing ({@code GET /publications/{id}/documents}).
 * Fetch the full document (content included) via
 * {@link social.surf.api.LongformApi#getDocument(String)} using {@link #uri()}.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record PublicationDocumentEntry(
        @JsonProperty("uri") String uri,
        @JsonProperty("title") String title,
        @JsonProperty("description") String description,
        @JsonProperty("path") String path,
        @JsonProperty("cover_image_url") String coverImageUrl,
        @JsonProperty("published_at") String publishedAt,
        @JsonProperty("tags") List<String> tags
) {
}
