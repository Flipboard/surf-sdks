package social.surf.api;

import java.util.Map;

/**
 * Self-service diagnostics and confidential debug-bundle sharing.
 *
 * <p>These endpoints live on the developer-portal host ({@link SurfClient#getDevportalUrl()},
 * default {@value SurfClient#DEFAULT_DEVPORTAL_URL}), not the {@code /v1} data API. A debug
 * bundle is a redacted, expiring snapshot you can share with Surf support to reproduce a
 * diagnosis without exposing a credential.
 *
 * <pre>{@code
 * // Diagnose this token's own app
 * Map<String, Object> diag = client.diagnostics.diagnose(null);
 *
 * // Mint a 15-minute bundle and share the returned token/url with support
 * Map<String, Object> bundle = client.diagnostics.createBundle(null, 15);
 * }</pre>
 */
public class DiagnosticsApi {

    private final SurfClient c;

    DiagnosticsApi(SurfClient client) {
        this.c = client;
    }

    /**
     * Structured diagnosis (findings + token health + usage + errors).
     *
     * <p>With an app API key, pass {@code null} for {@code appId} to diagnose that token's own app.
     */
    public Map<String, Object> diagnose(String appId) {
        String path = appId != null
                ? "/applications/" + SurfClient.encodePathSegment(appId) + "/diagnose"
                : "/diagnose";
        return c.getAbsolute(c.devportalUrl(path));
    }

    /**
     * Mint a redacted, expiring debug bundle. Returns {@code share_token} + {@code share_url}.
     *
     * <p>Pass {@code null} for {@code appId} to bundle this token's own app.
     */
    public Map<String, Object> createBundle(String appId, int ttlMinutes) {
        String path = appId != null
                ? "/applications/" + SurfClient.encodePathSegment(appId) + "/debug-bundle"
                : "/debug-bundle";
        return c.postAbsolute(c.devportalUrl(path), SurfClient.map("ttl_minutes", ttlMinutes));
    }

    /** Fetch a previously minted debug bundle by its share token. */
    public Map<String, Object> getBundle(String token) {
        return c.getAbsolute(c.devportalUrl("/debug-bundle/" + SurfClient.encodePathSegment(token)));
    }

    /** Revoke a debug bundle so its share token can no longer be redeemed. */
    public Map<String, Object> revokeBundle(String token) {
        return c.deleteAbsolute(c.devportalUrl("/debug-bundle/" + SurfClient.encodePathSegment(token)));
    }
}
