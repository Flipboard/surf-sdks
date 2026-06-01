package social.surf.api;

import social.surf.api.model.FeedSummary;
import social.surf.api.model.PostSummary;

import java.util.Map;
import java.util.stream.Stream;

import static social.surf.api.SurfClient.map;

/** AI-powered features ({@code use:ai} scope, 100 requests/day). */
public class AiApi {

    private final SurfClient c;

    AiApi(SurfClient client) {
        this.c = client;
    }

    /** Natural language search powered by NLWeb (default k=10). */
    public Map<String, Object> ask(String query) {
        return ask(query, 10, null, null);
    }

    /** Natural language search powered by NLWeb. */
    public Map<String, Object> ask(String query, int k) {
        return ask(query, k, null, null);
    }

    /** Natural language search with full options. */
    public Map<String, Object> ask(String query, int k, String schemaType, String feedId) {
        return c.get("/ai/ask", map("query", query, "k", k, "schema_type", schemaType, "feed_id", feedId));
    }

    /** AI-generated summary of a feed's recent posts (default limit 20). */
    public FeedSummary feedSummary(String surfId) {
        return feedSummary(surfId, 20);
    }

    /** AI-generated summary of a feed's recent posts. */
    public FeedSummary feedSummary(String surfId, int limit) {
        return c.getAs("/ai/feed-summary", map("surf_id", surfId, "limit", limit), FeedSummary.class);
    }

    /** AI-generated summary of a Bluesky post thread. */
    public PostSummary threadSummary(String postAt) {
        return c.getAs("/ai/thread-summary", map("post_at", postAt), PostSummary.class);
    }

    /**
     * Build a custom feed using AI (SSE stream).
     *
     * <p>Returns a lazy {@link Stream} of Server-Sent Event lines. Consume it fully or
     * close it to release the underlying connection.
     */
    public Stream<String> buildFeed(String prompt) {
        return buildFeed(prompt, null);
    }

    public Stream<String> buildFeed(String prompt, String feedId) {
        return c.postLines("/ai/feed-builder", map("prompt", prompt, "feed_id", feedId), 60);
    }
}
