package social.surf.api.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * The author/owner of a feed or post.
 *
 * <p>Mirrors {@code SurfAuthor} from the backend. {@link #service()} is a
 * server-computed value (bluesky, mastodon, patreon, threads, …).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Author(
        @JsonProperty("surf_id") String surfId,
        @JsonProperty("name") String name,
        @JsonProperty("description") String description,
        @JsonProperty("url") String url,
        @JsonProperty("host") String host,
        @JsonProperty("id") String id,
        @JsonProperty("image") FeedImageSize image,
        @JsonProperty("subscriberCount") Long subscriberCount,
        @JsonProperty("videoCount") Long videoCount,
        @JsonProperty("viewCount") Long viewCount,
        @JsonProperty("verifiedType") String verifiedType,
        @JsonProperty("account") String account,
        @JsonProperty("managed_account") Boolean managedAccount,
        @JsonProperty("managed_account_deactivated") Boolean managedAccountDeactivated,
        @JsonProperty("service") String service
) {
}
