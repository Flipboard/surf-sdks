package social.surf.api;

import com.fasterxml.jackson.databind.node.NullNode;
import social.surf.api.model.Sonar;
import social.surf.api.model.SonarChannel;
import social.surf.api.model.SonarMatch;
import social.surf.api.model.SonarMatchPage;
import social.surf.api.model.SonarPreview;
import social.surf.api.model.SonarSpec;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;

import static social.surf.api.SurfClient.encodePathSegment;
import static social.surf.api.SurfClient.map;

/**
 * Sonars: standing watches on the open social web ({@code read:sonars} / {@code write:sonars} scopes).
 *
 * <p>A Sonar is a saved {@link SonarSpec} — WHAT to listen for (a search query, topics, hashtags),
 * WHERE (surfaces: bluesky, mastodon, rss, podcast, youtube, leaflet) and content filters — matched
 * against every new post as it is indexed. Matches land in the Sonar's ledger and, for the
 * {@code instant} cadence with a {@code push} channel, arrive as a push notification. Preview a
 * spec before saving to see its volume.
 *
 * <pre>{@code
 * SonarSpec spec = SonarSpec.hashtags(List.of("#opensearch"), List.of("bluesky", "mastodon"));
 * SonarPreview preview = client.sonars.preview(spec, 7);
 * Sonar sonar = client.sonars.create("OpenSearch chatter", spec);
 * for (SonarMatch m : client.sonars.iterateMatches(sonar.id())) {
 *     System.out.println(m.matchedAt() + " " + m.postId());
 * }
 * }</pre>
 */
public class SonarsApi {

    private final SurfClient c;

    SonarsApi(SurfClient client) {
        this.c = client;
    }

    /** Create a Sonar with the defaults: enabled, {@code instant}, {@code [push]}, no cap. Live when the call returns. */
    public Sonar create(String name, SonarSpec spec) {
        return create(name, spec, null, null, null, null);
    }

    /**
     * Create a Sonar. Null delivery settings take the server defaults. A 400 names the spec
     * problem (empty subject, short term, unknown surface...).
     *
     * @param cadence  only {@code instant} is accepted today
     * @param channels only {@code push} is accepted today
     * @param dailyCap max pings per day; null for no cap
     */
    public Sonar create(String name, SonarSpec spec, Boolean enabled, String cadence, List<SonarChannel> channels,
                        Integer dailyCap) {
        return c.postAs("/sonars", map("name", name, "spec", spec, "enabled", enabled, "cadence", cadence,
                "channels", channels, "daily_cap", dailyCap), Sonar.class);
    }

    /** The caller's Sonars, newest first. */
    public List<Sonar> list() {
        return c.getListOf("/sonars", null, Sonar.class);
    }

    /** One Sonar. 404 when absent or someone else's. */
    public Sonar get(String id) {
        return c.getAs("/sonars/" + encodePathSegment(id), null, Sonar.class);
    }

    /**
     * PATCH a Sonar: only the fields present change ({@code name}, {@code spec}, {@code enabled},
     * {@code cadence}, {@code channels}, {@code daily_cap}). Null values are omitted on the wire,
     * so use {@link #clearDailyCap} to remove a cap. A new spec re-registers the live query only
     * when it compiles differently.
     */
    public Sonar update(String id, Map<String, Object> fields) {
        return c.patchAs("/sonars/" + encodePathSegment(id), fields, Sonar.class);
    }

    /** Rename a Sonar. */
    public Sonar rename(String id, String name) {
        return update(id, map("name", name));
    }

    /** Pause ({@code false}) or resume ({@code true}) a Sonar; the live query follows. */
    public Sonar setEnabled(String id, boolean enabled) {
        return update(id, map("enabled", enabled));
    }

    /** Replace the spec. */
    public Sonar updateSpec(String id, SonarSpec spec) {
        return update(id, map("spec", spec));
    }

    /** Remove the daily cap (sends an explicit {@code "daily_cap": null}). */
    public Sonar clearDailyCap(String id) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("daily_cap", NullNode.getInstance()); // a JSON null value, not an omitted field
        return update(id, body);
    }

    /** Delete a Sonar and its match history (204; returns an empty map). */
    public Map<String, Object> delete(String id) {
        return c.delete("/sonars/" + encodePathSegment(id));
    }

    /** The first page of the match ledger, newest first (server default 50). */
    public SonarMatchPage matches(String id) {
        return matches(id, null, null);
    }

    /**
     * One page of the match ledger, newest first.
     *
     * @param before the {@code nextBefore} cursor from the previous page; null for the first page
     * @param limit  page size, default 50, max 200
     */
    public SonarMatchPage matches(String id, Long before, Integer limit) {
        return c.getAs("/sonars/" + encodePathSegment(id) + "/matches", map("before", before, "limit", limit),
                SonarMatchPage.class);
    }

    /** Walk the whole match ledger, newest first, following {@code nextBefore} page by page. */
    public Iterable<SonarMatch> iterateMatches(String id) {
        return iterateMatches(id, null);
    }

    /** Walk the match ledger, newest first, stopping after {@code limit} matches (null = all). */
    public Iterable<SonarMatch> iterateMatches(String id, Integer limit) {
        return () -> new Iterator<>() {
            private final List<SonarMatch> buffer = new ArrayList<>();
            private Long before = null;
            private boolean exhausted = false;
            private int yielded = 0;

            @Override
            public boolean hasNext() {
                if (limit != null && yielded >= limit) {
                    return false;
                }
                while (buffer.isEmpty() && !exhausted) {
                    Integer pageSize = limit == null ? null : Math.min(200, limit - yielded);
                    SonarMatchPage page = matches(id, before, pageSize);
                    if (page.matches() != null) {
                        buffer.addAll(page.matches());
                    }
                    before = page.nextBefore();
                    exhausted = before == null;
                }
                return !buffer.isEmpty();
            }

            @Override
            public SonarMatch next() {
                if (!hasNext()) {
                    throw new NoSuchElementException();
                }
                yielded++;
                return buffer.remove(0);
            }
        };
    }

    /** Preview over the default trailing window (30 days). */
    public SonarPreview preview(SonarSpec spec) {
        return preview(spec, null);
    }

    /**
     * What a spec would have matched over the trailing window (1-30 days): total, per-day
     * histogram and five newest samples. The same compiled query the matcher uses, so the number
     * is a real forecast; cached server-side for 15 minutes per compiled spec. Requires
     * {@code write:sonars}.
     */
    public SonarPreview preview(SonarSpec spec, Integer days) {
        return c.postAs("/sonars/preview" + (days == null ? "" : "?days=" + days), spec, SonarPreview.class);
    }
}
