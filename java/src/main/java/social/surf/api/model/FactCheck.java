package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * Result of an AI fact-check ({@code POST /ai/fact-check}).
 *
 * <p>Mirrors the backend fact-check response. Wire keys are camelCase, e.g.
 * {@code postSurfId}, {@code citationIndices}, {@code surfId}.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record FactCheck(
        @JsonProperty("postSurfId") String postSurfId,
        @JsonProperty("verdict") String verdict,
        @JsonProperty("answer") String answer,
        @JsonProperty("paragraphs") List<Paragraph> paragraphs,
        @JsonProperty("citations") List<Citation> citations
) {

    /** A paragraph of the fact-check answer, with indices into {@link FactCheck#citations()}. */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Paragraph(
            @JsonProperty("text") String text,
            @JsonProperty("citationIndices") List<Integer> citationIndices
    ) {
    }

    /** A source cited by the fact-check. */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Citation(
            @JsonProperty("type") String type,
            @JsonProperty("url") String url,
            @JsonProperty("surfId") String surfId
    ) {
    }
}
