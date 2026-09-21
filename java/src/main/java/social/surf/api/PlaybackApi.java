package social.surf.api;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Playback positions: resume where you left off, on whichever device you pick up
 * ({@code read:playback} / {@code write:playback} scopes; a coarse {@code read} /
 * {@code write} OAuth grant satisfies them).
 *
 * <p>A position belongs to the ACCOUNT rather than the device, so reporting from a
 * phone and then opening a tablet resumes in the same place.
 *
 * <p>Reporting also feeds the recently-played signal behind new-episode
 * notifications: a show played in the last 90 days is one Surf treats as followed.
 * That is a consequence of reporting, not a second call to make.
 *
 * <pre>{@code
 * client.playback.report("post-123", "surf/podcast/abc", 125_000L, 3_600_000L, null);
 *
 * for (Map<String, Object> item : client.playback.recent(10)) {
 *     System.out.println(item.get("post_id") + " " + item.get("position_ms"));
 * }
 * }</pre>
 */
public class PlaybackApi {

    /** The server's own cap on one batch; a larger list is a 400. */
    private static final int MAX_BATCH = 100;

    private final SurfClient c;

    PlaybackApi(SurfClient client) {
        this.c = client;
    }

    /**
     * Record where the listener got to.
     *
     * @param postId     the episode's post id (&lt;= 255 characters)
     * @param feedSurfId the show the episode belongs to (&lt;= 512 characters). Required:
     *                   the recently-played signal is about the show, and the server does
     *                   not resolve the episode to it.
     * @param positionMs milliseconds from the start. {@code 0} is a real value.
     * @param durationMs the episode's length when known, or {@code null}. Omitting it leaves
     *                   whatever an earlier report established rather than clearing it.
     * @param completed  {@code true} once the end is reached, or {@code null} to say nothing.
     *                   Sticky server-side: a later report from earlier in the episode does
     *                   not un-finish it.
     */
    public void report(String postId, String feedSurfId, long positionMs,
                       Long durationMs, Boolean completed) {
        c.post("/playback", body(postId, feedSurfId, positionMs, durationMs, completed));
    }

    /** Record a position, saying nothing about duration or completion. */
    public void report(String postId, String feedSurfId, long positionMs) {
        report(postId, feedSurfId, positionMs, null, null);
    }

    /**
     * Report a whole session at once, for a client coming back online. Up to 100 items,
     * each built with {@link #item}; applied in the order given, so two reports for one
     * episode settle correctly.
     *
     * <p>Note that {@code played_at} is stamped when the report ARRIVES, so a batch handed
     * over after a spell offline carries the hand-over time rather than the listening time.
     */
    public void reportBatch(List<Map<String, Object>> items) {
        if (items == null || items.isEmpty()) {
            return; // nothing to say costs no round trip
        }
        if (items.size() > MAX_BATCH) {
            throw new IllegalArgumentException(
                    "A playback batch takes at most " + MAX_BATCH + " items, got " + items.size());
        }
        c.post("/playback/batch", Map.of("items", items));
    }

    /**
     * One item for {@link #reportBatch}, with the same omission rules as {@link #report}:
     * a null {@code durationMs} or {@code completed} is left out rather than sent as a
     * zero or a false.
     */
    public static Map<String, Object> item(String postId, String feedSurfId, long positionMs,
                                           Long durationMs, Boolean completed) {
        return body(postId, feedSurfId, positionMs, durationMs, completed);
    }

    /** One batch item, saying nothing about duration or completion. */
    public static Map<String, Object> item(String postId, String feedSurfId, long positionMs) {
        return body(postId, feedSurfId, positionMs, null, null);
    }

    /** The account's most recently played episodes, newest first (max 200). */
    public List<Map<String, Object>> recent(int limit) {
        Map<String, Object> params = new LinkedHashMap<>();
        if (limit > 0) {
            params.put("limit", limit);
        }
        return c.getMapList("/playback", params);
    }

    /** The account's most recently played episodes, newest first, at the server's default page size. */
    public List<Map<String, Object>> recent() {
        return recent(0);
    }

    /**
     * Positions for specific episodes, so a list costs one call rather than one per row.
     * Up to 100 ids.
     *
     * <p>An episode with no stored position is ABSENT from the result rather than returned
     * as zero, which could not be told from "started and stopped at the beginning".
     */
    public List<Map<String, Object>> positions(List<String> postIds) {
        List<String> ids = new ArrayList<>();
        if (postIds != null) {
            for (String id : postIds) {
                if (id != null && !id.isBlank()) {
                    ids.add(id);
                }
            }
        }
        if (ids.isEmpty()) {
            return new ArrayList<>(); // an empty post_id is a 400, not an empty answer
        }
        return c.getMapList("/playback/positions", Map.of("post_id", ids));
    }

    private static Map<String, Object> body(String postId, String feedSurfId, long positionMs,
                                            Long durationMs, Boolean completed) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("post_id", postId);
        body.put("feed_surf_id", feedSurfId);
        body.put("position_ms", positionMs);
        if (durationMs != null) {
            body.put("duration_ms", durationMs);
        }
        if (completed != null) {
            body.put("completed", completed);
        }
        return body;
    }
}
