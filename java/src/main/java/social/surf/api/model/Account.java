package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * The authenticated user's Surf account.
 *
 * <p>Mirrors {@code SurfAccountInternal} from the backend. {@code feed_memberships}
 * is a list of SurfId strings (the backend serializes SurfId as a plain string).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Account(
        @JsonProperty("id") String id,
        @JsonProperty("email") String email,
        @JsonProperty("username") String username,
        @JsonProperty("verified") Boolean verified,
        @JsonProperty("display_name") String displayName,
        @JsonProperty("description") String description,
        @JsonProperty("avatar") String avatar,
        @JsonProperty("authors") List<Author> authors,
        @JsonProperty("feed_memberships") List<String> feedMemberships,
        @JsonProperty("roles") List<String> roles,
        @JsonProperty("surf_id") String surfId
) {
}
