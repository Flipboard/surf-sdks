package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * A link shown on a user's profile.
 *
 * <p>Mirrors {@code SurfAccountProfileLink} from the backend.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ProfileLink(
        @JsonProperty("id") String id,
        @JsonProperty("account_id") String accountId,
        @JsonProperty("account_type") String accountType,
        @JsonProperty("created") Long created,
        @JsonProperty("last_modified") Long lastModified,
        @JsonProperty("account_uri") String accountUri,
        @JsonProperty("show_icon") Boolean showIcon,
        @JsonProperty("show_in_feed") Boolean showInFeed,
        @JsonProperty("title") String title,
        @JsonProperty("url") String url,
        @JsonProperty("icon") String icon
) {
}
