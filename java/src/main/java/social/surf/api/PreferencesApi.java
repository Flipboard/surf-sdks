package social.surf.api;

import java.util.Map;

/** Preferences operations ({@code read:preferences} / {@code write:preferences} scopes). */
public class PreferencesApi {

    private final SurfClient c;

    PreferencesApi(SurfClient client) {
        this.c = client;
    }

    /** Get user preferences. */
    public Map<String, Object> get() {
        return c.get("/preferences/account");
    }

    /** Update user preferences ({@code write:preferences}). Merge-patch semantics. */
    public Map<String, Object> update(Map<String, Object> preferences) {
        return c.patch("/preferences/account", preferences);
    }
}
