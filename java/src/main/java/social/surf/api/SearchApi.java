package social.surf.api;

import java.util.Map;

import static social.surf.api.SurfClient.map;

/**
 * Search operations ({@code read:search} scope).
 *
 * <p>The consolidated {@code /search} endpoint supports
 * {@code type=feeds|posts|accounts|podcasts|rss}.
 */
public class SearchApi {

    private final SurfClient c;

    SearchApi(SurfClient client) {
        this.c = client;
    }

    /** Unified search (default type {@code feeds}, limit 20). */
    public Map<String, Object> search(String query) {
        return search(query, "feeds", 20);
    }

    /** Unified search with a type. */
    public Map<String, Object> search(String query, String type) {
        return search(query, type, 20);
    }

    /** Unified search. type: feeds, posts, accounts, podcasts, rss. */
    public Map<String, Object> search(String query, String type, int limit) {
        return c.get("/search", map("q", query, "type", type, "limit", limit));
    }

    public Map<String, Object> feeds(String query) {
        return search(query, "feeds", 20);
    }

    public Map<String, Object> feeds(String query, int limit) {
        return search(query, "feeds", limit);
    }

    public Map<String, Object> posts(String query) {
        return search(query, "posts", 20);
    }

    public Map<String, Object> posts(String query, int limit) {
        return search(query, "posts", limit);
    }

    public Map<String, Object> accounts(String query) {
        return search(query, "accounts", 20);
    }

    public Map<String, Object> accounts(String query, int limit) {
        return search(query, "accounts", limit);
    }

    public Map<String, Object> podcasts(String query) {
        return search(query, "podcasts", 20);
    }

    public Map<String, Object> podcasts(String query, int limit) {
        return search(query, "podcasts", limit);
    }

    /** Discover feeds (default type {@code recommended}, limit 20). */
    public Map<String, Object> discover() {
        return discover("recommended", null, 20);
    }

    /** Discover feeds. type: recommended, similar, interests. */
    public Map<String, Object> discover(String type) {
        return discover(type, null, 20);
    }

    /** Discover feeds with full options. */
    public Map<String, Object> discover(String type, String surfId, int limit) {
        return c.get("/search/discover", map("type", type, "surf_id", surfId, "limit", limit));
    }
}
