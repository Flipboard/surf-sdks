package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * Writable shape for adding an operator (source) to a custom feed.
 *
 * <p>The user-supplied subset of {@link FeedOperator} — only the fields the server
 * accepts on create. Server-assigned fields ({@code id}, {@code created},
 * {@code last_modified}) live on {@link FeedOperator} and are populated in the
 * response.
 *
 * <p>Common case:
 * <pre>{@code
 * NewFeedOperator.source("surf/hashtag/cats")
 * }</pre>
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record NewFeedOperator(
        @JsonProperty("surfId") String surfId,
        @JsonProperty("operator") Operator operator,
        @JsonProperty("filters") List<FeedFilter> filters
) {
    /** A {@link Operator#source source} operator for {@code surfId} with no filters. */
    public static NewFeedOperator source(String surfId) {
        return new NewFeedOperator(surfId, Operator.source, null);
    }

    /** An operator of the given role for {@code surfId} with no filters. */
    public static NewFeedOperator of(String surfId, Operator operator) {
        return new NewFeedOperator(surfId, operator, null);
    }
}
