package social.surf.api;

import social.surf.api.model.Publication;

import java.util.List;
import java.util.Map;

import static social.surf.api.SurfClient.map;

/**
 * Search operations ({@code read:search} scope).
 *
 * <p>Each search type maps to its own backend endpoint (the unified {@code /search}
 * endpoint is deprecated): {@code posts} -> {@code /search/posts},
 * {@code feeds}/{@code podcasts} -> {@code /search/maestra/feeds},
 * {@code accounts} -> {@code /search/bluesky/searchActors},
 * {@code rss} -> {@code /search/rss/search}.
 */
public class SearchApi {

    private static final Map<String, String> PATHS = Map.of(
        "posts", "/search/posts",
        "feeds", "/search/maestra/feeds",
        "accounts", "/search/bluesky/searchActors",
        "podcasts", "/search/maestra/feeds",
        "rss", "/search/rss/search");

    private final SurfClient c;

    SearchApi(SurfClient client) {
        this.c = client;
    }

    /** Search (default type {@code feeds}, limit 20). */
    public Map<String, Object> search(String query) {
        return search(query, "feeds", 20);
    }

    /** Search with a type. */
    public Map<String, Object> search(String query, String type) {
        return search(query, type, 20);
    }

    /** Search. type: feeds, posts, accounts, podcasts, rss. */
    public Map<String, Object> search(String query, String type, int limit) {
        String path = PATHS.get(type);
        if (path == null) {
            throw new IllegalArgumentException(
                "unsupported search type: '" + type + "'; supported types are " + PATHS.keySet());
        }
        return c.get(path, map("q", query, "limit", limit));
    }

    public Map<String, Object> feeds(String query) {
        return search(query, "feeds", 20);
    }

    public Map<String, Object> feeds(String query, int limit) {
        return search(query, "feeds", limit);
    }

    /**
     * Search posts. The query (all {@code posts} overloads) supports exact phrases in
     * double quotes ({@code "climate change"}) and boolean operators {@code AND}/{@code &&}
     * and {@code OR}/{@code ||} between terms ({@code cats AND dogs}); the word forms are
     * uppercase-only, plain keywords are implicit AND.
     */
    public Map<String, Object> posts(String query) {
        return search(query, "posts", 20);
    }

    public Map<String, Object> posts(String query, int limit) {
        return search(query, "posts", limit);
    }

    /**
     * Search posts with the post-only options. {@code sort}: "recent" (newest-first) or
     * "top" (relevance/engagement); {@code since}: recency window ("24h", "7d", "30m",
     * "90s") — pair with sort="top" for a trending result; {@code automated}: {@code false}
     * drops bot/bridge-account posts. Any argument may be {@code null} to omit it.
     */
    public Map<String, Object> posts(String query, int limit, String sort, String since, Boolean automated) {
        return posts(query, limit, sort, since, automated, null, null);
    }

    /**
     * Search posts with the full set of post-only options. In addition to {@code sort},
     * {@code since}, and {@code automated} (see the shorter overload): {@code safety}
     * "sfw" drops posts flagged NSFW at ingest server-side, applied before the limit so
     * you get a full page of safe posts ("all" returns everything); {@code excludeReplies}
     * {@code true} drops replies into other threads, keeping standalone and quote posts.
     * Any argument may be {@code null} to omit it.
     */
    public Map<String, Object> posts(String query, int limit, String sort, String since, Boolean automated,
                                     String safety, Boolean excludeReplies) {
        return c.get("/search/posts", map(
            "q", query,
            "limit", limit,
            "sort", sort,
            "since", since,
            "automated", automated == null ? null : String.valueOf(automated),
            "safety", safety,
            "exclude_replies", excludeReplies == null ? null : String.valueOf(excludeReplies)));
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

    /** Search longform publications (standard.site / Leaflet), default count 20. */
    public List<Publication> publications(String query) {
        return publications(query, 20, 0);
    }

    /** Search longform publications with a page size. */
    public List<Publication> publications(String query, int count) {
        return publications(query, count, 0);
    }

    /**
     * Search longform publications (standard.site / Leaflet) with full options.
     * Same endpoint as {@link LongformApi#searchPublications(String, int, int)}.
     *
     * @param query search query (required)
     * @param count page size (default 20, max 100)
     * @param from  result offset (default 0)
     */
    public List<Publication> publications(String query, int count, int from) {
        return c.getListOf("/search/publications",
                map("q", query, "count", count, "from", from),
                Publication.class);
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
