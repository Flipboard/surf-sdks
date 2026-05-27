package social.surf.api;

import java.util.Map;

import static social.surf.api.SurfClient.map;

/** Content processing ({@code read:feeds} scope). */
public class ContentApi {

    private final SurfClient c;

    ContentApi(SurfClient client) {
        this.c = client;
    }

    /** Resolve/unshorten a URL. Returns final URL and redirect chain. */
    public Map<String, Object> resolve(String url) {
        return c.get("/content/resolve", map("url", url));
    }

    /** Extract structured content from a URL (default type {@code article}). */
    public Map<String, Object> extract(String url) {
        return extract(url, "article");
    }

    /** Extract structured content from a URL (article, image, video, audio). */
    public Map<String, Object> extract(String url, String type) {
        return c.get("/content/extract", map("url", url, "type", type));
    }

    /** Detect the language of content at a URL. */
    public Map<String, Object> language(String url) {
        return c.get("/content/language", map("url", url));
    }

    /** Get auto-assigned topics for a URL. */
    public Map<String, Object> topics(String url) {
        return c.get("/content/topics", map("url", url));
    }

    /** Get full enrichment data for a post (topics, claim_score, NSFW, etc.). */
    public Map<String, Object> enrich(String postId) {
        return c.get("/content/enrich", map("post_id", postId));
    }
}
