package social.surf.api;

import social.surf.api.model.Feed;

import java.util.List;
import java.util.Map;

import static social.surf.api.SurfClient.map;

/** Feed operations ({@code read:feeds} scope). */
public class FeedsApi {

    private final SurfClient c;

    FeedsApi(SurfClient client) {
        this.c = client;
    }

    /** Get feed metadata. */
    public Feed get(String surfId) {
        return c.getAs("/feed", map("surf_id", surfId), Feed.class);
    }

    /** Get posts from a feed (default limit 20). Posts are dynamic Mastodon-format JSON. */
    public List<Map<String, Object>> getPosts(String surfId) {
        return getPosts(surfId, 20, null, null, null);
    }

    /** Get posts from a feed. */
    public List<Map<String, Object>> getPosts(String surfId, int limit) {
        return getPosts(surfId, limit, null, null, null);
    }

    /** Get posts from a feed with full options. Null optional args are omitted. */
    public List<Map<String, Object>> getPosts(String surfId, int limit, String cursor, String sort, String services) {
        return c.getMapList("/feed/posts", map(
                "surf_id", surfId, "limit", limit, "cursor", cursor, "sort", sort, "services", services));
    }

    /** Get a single post by ID. */
    public Map<String, Object> getPost(String postId) {
        return getPost(postId, false);
    }

    /** Get a single post by ID, optionally with thread context. */
    public Map<String, Object> getPost(String postId, boolean thread) {
        return c.get("/post", map("id", postId, "thread", String.valueOf(thread)));
    }

    /** Get feeds the authenticated user follows (default limit 50). */
    public List<Map<String, Object>> getFollowing() {
        return getFollowing(50);
    }

    /** Get feeds the authenticated user follows. */
    public List<Map<String, Object>> getFollowing(int limit) {
        return c.getMapList("/feed/following", map("limit", limit));
    }

    /** Get the user's speed dial feeds. */
    public Map<String, Object> getSpeedDial() {
        return c.get("/feed/speeddial");
    }

    /** Get RSS XML for a feed. */
    public String getRss(String surfId) {
        return c.getText("/feed/posts", map("surf_id", surfId, "format", "rss"));
    }

    // ------------------------------------------------------------------
    // Write operations (require write:statuses scope)
    // ------------------------------------------------------------------

    /** Create a new post ({@code write:statuses}). */
    public Map<String, Object> createPost(String status) {
        return createPost(status, "public", null, false, null, null);
    }

    /** Create a new post with a visibility. */
    public Map<String, Object> createPost(String status, String visibility) {
        return createPost(status, visibility, null, false, null, null);
    }

    /** Create a new post with full options. */
    public Map<String, Object> createPost(String status, String visibility, String inReplyToId,
                                          boolean sensitive, String spoilerText, String language) {
        Map<String, Object> body = map(
                "status", status,
                "visibility", visibility,
                "in_reply_to_id", inReplyToId,
                "sensitive", sensitive ? Boolean.TRUE : null,
                "spoiler_text", spoilerText,
                "language", language);
        return c.post("/statuses", body);
    }

    /** Favorite a post ({@code write:statuses}). */
    public Map<String, Object> favourite(String postId) {
        return c.post("/statuses/" + postId + "/favourite");
    }

    /** Unfavorite a post ({@code write:statuses}). */
    public Map<String, Object> unfavourite(String postId) {
        return c.post("/statuses/" + postId + "/unfavourite");
    }

    /** Boost/reblog a post ({@code write:statuses}). */
    public Map<String, Object> boost(String postId) {
        return c.post("/statuses/" + postId + "/reblog");
    }

    /** Unboost a post ({@code write:statuses}). */
    public Map<String, Object> unboost(String postId) {
        return c.post("/statuses/" + postId + "/unreblog");
    }

    /** Bookmark a post ({@code write:statuses}). */
    public Map<String, Object> bookmark(String postId) {
        return c.post("/statuses/" + postId + "/bookmark");
    }

    /** Delete own post ({@code write:statuses}). */
    public Map<String, Object> deletePost(String postId) {
        return c.delete("/statuses/" + postId);
    }
}
