package social.surf.api;

import social.surf.api.model.Account;
import social.surf.api.model.ProfileLink;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static social.surf.api.SurfClient.map;

/** Account operations ({@code read:account} / {@code write:account} scopes). */
public class AccountApi {

    private final SurfClient c;

    AccountApi(SurfClient client) {
        this.c = client;
    }

    /** Get the authenticated user's account info. */
    public Account get() {
        return c.getAs("/account", null, Account.class);
    }

    /** Update account fields ({@code write:account}). */
    public Account update(Map<String, Object> fields) {
        return c.putAs("/account", fields, Account.class);
    }

    /** Look up an account by handle (e.g. user.bsky.social or user@mastodon.social). */
    public Map<String, Object> lookup(String account) {
        return c.get("/account/lookup", map("account", account));
    }

    /** Get all profile links. */
    public List<ProfileLink> getLinks() {
        return c.getListOf("/account/links", null, ProfileLink.class);
    }

    /** Add a profile link ({@code write:account}). */
    public ProfileLink addLink(String title, String url) {
        return addLink(title, url, null);
    }

    /** Add a profile link with an icon ({@code write:account}). */
    public ProfileLink addLink(String title, String url, String icon) {
        return c.postAs("/account/links", map("title", title, "url", url, "icon", icon), ProfileLink.class);
    }

    /** Update a profile link ({@code write:account}). */
    public ProfileLink updateLink(String linkId, Map<String, Object> fields) {
        Map<String, Object> body = new LinkedHashMap<>(fields);
        body.put("id", linkId);
        return c.putAs("/account/links/" + linkId, body, ProfileLink.class);
    }

    /** Delete a profile link ({@code write:account}). */
    public Map<String, Object> deleteLink(String linkId) {
        return c.delete("/account/links/" + linkId);
    }

    /** Get OAuth-authorized third-party apps ({@code read:account}). */
    public Map<String, Object> getConnectedApps() {
        return c.get("/account/connected-apps");
    }

    /** Revoke a third-party app's OAuth access ({@code write:account}). */
    public Map<String, Object> revokeConnectedApp(long authorizationId) {
        return c.post("/account/connected-apps/" + authorizationId + "/revoke");
    }
}
