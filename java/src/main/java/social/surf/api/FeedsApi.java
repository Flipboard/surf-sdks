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
        return getPosts(surfId, limit, cursor, sort, services, null);
    }

    /**
     * Get posts from a feed with full options, including a recency window.
     * {@code since} is a digest cutoff — a rolling duration ("24h", "7d", "30m", "90s", or a
     * bare number of seconds) or an absolute ISO 8601 timestamp; only posts created at or after
     * the cutoff are returned. Null optional args are omitted.
     */
    public List<Map<String, Object>> getPosts(String surfId, int limit, String cursor, String sort, String services, String since) {
        return c.getMapList("/feed/posts", map(
                "surf_id", surfId, "limit", limit, "cursor", cursor, "sort", sort, "services", services, "since", since));
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
    public List<Map<String, Object>> getFollowing(String surfId) {
        return getFollowing(surfId, 50);
    }

    /**
     * Public custom feeds that include {@code surfId} as a source (a reverse lookup). Not the
     * caller's subscriptions; those are {@code feedPins} in {@code preferences.get()}.
     */
    public List<Map<String, Object>> getFollowing(String surfId, int limit) {
        List<Map<String, Object>> r = c.getMapList("/feed/following", map("surf_id", surfId, "limit", limit));
        return r == null ? List.of() : r;
    }

    /** A single post by id ({@code GET /statuses/{id}}); {@code at://} ids are encoded for you. */
    public Map<String, Object> getStatus(String postId) {
        return getStatus(postId, null);
    }

    public Map<String, Object> getStatus(String postId, String service) {
        return c.get(servicePath("/statuses/" + enc(postId), service));
    }

    /** The thread around a post: {@code {ancestors, descendants}}; the subject post is not included. */
    public Map<String, Object> getStatusContext(String postId) {
        return getStatusContext(postId, null);
    }

    public Map<String, Object> getStatusContext(String postId, String service) {
        return c.get(servicePath("/statuses/" + enc(postId) + "/context", service));
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
    //
    // All write methods accept an optional `service` parameter to target a
    // specific linked account: "bluesky" or "mastodon". If null, defaults
    // to the first available (prefers Bluesky).
    // ------------------------------------------------------------------

    /** Create a new post ({@code write:statuses}). */
    public Map<String, Object> createPost(String status) {
        return createPost(status, "public", null, false, null, null, null);
    }

    /** Create a new post with a visibility. */
    public Map<String, Object> createPost(String status, String visibility) {
        return createPost(status, visibility, null, false, null, null, null);
    }

    /** Create a new post targeting a specific service. */
    public Map<String, Object> createPost(String status, String visibility, String service) {
        return createPost(status, visibility, null, false, null, null, service);
    }

    /** Create a new post with full options. */
    public Map<String, Object> createPost(String status, String visibility, String inReplyToId,
                                          boolean sensitive, String spoilerText, String language,
                                          String service) {
        return createPost(status, visibility, inReplyToId, sensitive, spoilerText, language, service, null);
    }

    /**
     * Create a new post with full options and media.
     *
     * <p>{@code service} picks the linked account ("bluesky" or "mastodon"; default Bluesky, then
     * Mastodon). Replying to a Mastodon post (numeric {@code inReplyToId}) requires "mastodon".
     * {@code visibility} is honoured on Mastodon only: Bluesky posts are always public and a
     * non-public value is rejected with 400. {@code mediaIds} come from
     * {@link MediaApi#uploadAttachment} (max 4).
     */
    public Map<String, Object> createPost(String status, String visibility, String inReplyToId,
                                          boolean sensitive, String spoilerText, String language,
                                          String service, List<String> mediaIds) {
        Map<String, Object> body = map(
                "status", status,
                "visibility", visibility,
                "in_reply_to_id", inReplyToId,
                "media_ids", mediaIds == null || mediaIds.isEmpty() ? null : mediaIds,
                "sensitive", sensitive ? Boolean.TRUE : null,
                "spoiler_text", spoilerText,
                "language", language);
        return c.post(servicePath("/statuses", service), body);
    }

    /** Favorite a post ({@code write:statuses}). */
    public Map<String, Object> favourite(String postId) {
        return favourite(postId, null);
    }

    /** Favorite a post targeting a specific service. */
    public Map<String, Object> favourite(String postId, String service) {
        return c.post(servicePath("/statuses/" + enc(postId) + "/favourite", service));
    }

    /** Unfavorite a post ({@code write:statuses}). */
    public Map<String, Object> unfavourite(String postId) {
        return unfavourite(postId, null);
    }

    public Map<String, Object> unfavourite(String postId, String service) {
        return c.post(servicePath("/statuses/" + enc(postId) + "/unfavourite", service));
    }

    /** Boost/reblog a post ({@code write:statuses}). */
    public Map<String, Object> boost(String postId) {
        return boost(postId, null);
    }

    public Map<String, Object> boost(String postId, String service) {
        return c.post(servicePath("/statuses/" + enc(postId) + "/reblog", service));
    }

    /** Unboost a post ({@code write:statuses}). */
    public Map<String, Object> unboost(String postId) {
        return unboost(postId, null);
    }

    public Map<String, Object> unboost(String postId, String service) {
        return c.post(servicePath("/statuses/" + enc(postId) + "/unreblog", service));
    }

    /** Bookmark a post ({@code write:statuses}). */
    public Map<String, Object> bookmark(String postId) {
        return bookmark(postId, null);
    }

    public Map<String, Object> bookmark(String postId, String service) {
        return c.post(servicePath("/statuses/" + enc(postId) + "/bookmark", service));
    }

    /** Unbookmark a post ({@code write:statuses}). */
    public Map<String, Object> unbookmark(String postId) {
        return unbookmark(postId, null);
    }

    public Map<String, Object> unbookmark(String postId, String service) {
        return c.post(servicePath("/statuses/" + enc(postId) + "/unbookmark", service));
    }

    /** Pin one of your own posts to your profile ({@code write:statuses}). */
    public Map<String, Object> pin(String postId) {
        return pin(postId, null);
    }

    public Map<String, Object> pin(String postId, String service) {
        return c.post(servicePath("/statuses/" + enc(postId) + "/pin", service));
    }

    /** Unpin a post from your profile ({@code write:statuses}). */
    public Map<String, Object> unpin(String postId) {
        return unpin(postId, null);
    }

    public Map<String, Object> unpin(String postId, String service) {
        return c.post(servicePath("/statuses/" + enc(postId) + "/unpin", service));
    }

    /** Delete own post ({@code write:statuses}). */
    public Map<String, Object> deletePost(String postId) {
        return deletePost(postId, null);
    }

    public Map<String, Object> deletePost(String postId, String service) {
        return c.delete(servicePath("/statuses/" + enc(postId), service));
    }

    /** Append {@code ?service=bluesky|mastodon} if non-null. */
    private static String servicePath(String path, String service) {
        return service != null ? path + "?service=" + service : path;
    }

    /**
     * Percent-encode a post id for use as a single URL path segment. Surf post ids are
     * Bluesky AT-URIs ({@code at://did:plc:.../app.bsky.feed.post/...}) whose {@code :}
     * and {@code /} characters must be escaped, or the gateway splits them into extra
     * path segments and returns "Route not found".
     */
    private static String enc(String postId) {
        return SurfClient.encodePathSegment(postId);
    }
}
