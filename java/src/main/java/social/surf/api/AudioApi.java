package social.surf.api;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Map;

import static social.surf.api.SurfClient.map;

/** Audio operations ({@code read:audio} / {@code write:audio} scopes). */
public class AudioApi {

    private final SurfClient c;

    AudioApi(SurfClient client) {
        this.c = client;
    }

    // Radio

    /** List radio stations for the authenticated user. */
    public Map<String, Object> listStations() {
        return c.get("/audio/radio/stations");
    }

    /** Get a radio station by ID. */
    public Map<String, Object> getStation(String stationId) {
        return c.get("/audio/radio/stations/" + stationId);
    }

    /** Create a radio station from a feed ({@code write:audio}). */
    public Map<String, Object> createStation(String feedSurfId) {
        return createStation(feedSurfId, null);
    }

    /** Create a radio station from a feed with a title ({@code write:audio}). */
    public Map<String, Object> createStation(String feedSurfId, String title) {
        return c.post("/audio/radio/stations", map("feed_surf_id", feedSurfId, "title", title));
    }

    /** Generate a new radio program ({@code write:audio}). */
    public Map<String, Object> generateProgram(String stationId) {
        return c.post("/audio/radio/stations/" + stationId + "/generate");
    }

    /** Get a radio program manifest with signed audio URLs. */
    public Map<String, Object> getProgram(String programId) {
        return c.get("/audio/radio/programs/" + programId);
    }

    // Briefing

    /** Generate a new daily briefing ({@code write:audio}). */
    public Map<String, Object> generateBriefing() {
        return c.post("/audio/briefing/generate");
    }

    /** Get the latest briefing. */
    public Map<String, Object> getBriefing() {
        return c.get("/audio/briefing/latest");
    }

    /** Get a briefing by ID. */
    public Map<String, Object> getBriefing(String briefingId) {
        if (briefingId == null) {
            return getBriefing();
        }
        return c.get("/audio/briefing/" + briefingId);
    }

    // Transcript

    /** Get a signed URL for an episode transcript. */
    public Map<String, Object> getTranscript(String episodeUrl) {
        return c.get("/audio/transcript", map("episode_url", episodeUrl));
    }

    /**
     * Get structured, AI-generated show notes for a transcribed episode: summary, topics,
     * people, organizations, timestamped outline, key takeaways, and chapters, plus a
     * {@code signed_url} for the raw show-notes JSON. Throws {@link SurfNotFoundError} if
     * show notes have not been generated for the episode yet.
     */
    public Map<String, Object> getShowNotes(String episodeUrl) {
        return getShowNotes(episodeUrl, null);
    }

    /**
     * Get show notes in a specific language (e.g. {@code "en"}, {@code "es"}) for
     * translated notes; pass {@code null} for the episode's original language.
     */
    public Map<String, Object> getShowNotes(String episodeUrl, String language) {
        return c.get("/audio/transcripts/show-notes", map("episode_url", episodeUrl, "language", language));
    }

    // Podcast intelligence

    /**
     * SHA1 hex of a full episode audio URL. {@code episode_url_hash} is the episode's
     * stable ID across the podcast intelligence endpoints (episode search results, guest
     * appearances, mentions, and the sponsor/ads database).
     */
    public static String episodeUrlHash(String episodeUrl) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-1");
            byte[] digest = md.digest(episodeUrl.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            // SHA-1 is required on every conforming JVM.
            throw new IllegalStateException("SHA-1 MessageDigest unavailable", e);
        }
    }

    /** Semantic podcast episode search with the default limit (20). See the full overload. */
    public Map<String, Object> searchPodcastEpisodes(String q) {
        return searchPodcastEpisodes(q, null, 20);
    }

    /**
     * Semantic search across transcribed podcast episodes ({@code read:audio}). Episodes
     * matching the natural-language query are found via embedding similarity over
     * transcript chunks (no keyword overlap required); each result carries the matching
     * chunk's time range ({@code chunk_start_seconds}/{@code chunk_end_seconds}), a text
     * {@code preview}, and a similarity {@code score} (0-1), plus {@code episode_url_hash}
     * (SHA1 hex of the full audio URL — see {@link #episodeUrlHash}). {@code flyfId}
     * ({@code null} to omit) restricts to one podcast (SHA1 hex of the full RSS feed URL);
     * {@code limit} default 20, max 100.
     */
    public Map<String, Object> searchPodcastEpisodes(String q, String flyfId, int limit) {
        return c.get("/audio/episodes/search", map("q", q, "flyf_id", flyfId, "limit", limit));
    }

    /** Podcast guest search with the default limit (20). See the full overload. */
    public Map<String, Object> searchPodcastGuests(String q) {
        return searchPodcastGuests(q, 20);
    }

    /**
     * Search podcast guests and hosts by name with fuzzy matching ({@code read:audio}).
     * Each match includes known profile details (title, organization, social handles) and
     * detected episode {@code appearances} with role, confidence, and speaking time.
     * {@code limit} default 20, max 100.
     */
    public Map<String, Object> searchPodcastGuests(String q, int limit) {
        return c.get("/audio/guests/search", map("q", q, "limit", limit));
    }

    /** Entity mentions with defaults (no filters, limit 20, offset 0). See the full overload. */
    public Map<String, Object> getPodcastMentions(String entity) {
        return getPodcastMentions(entity, null, null, 20, 0);
    }

    /**
     * Find podcast episodes mentioning a person, organization, or location
     * ({@code read:audio}; case-insensitive NER over transcripts). Each row covers one
     * episode with the mention count, first mention time, and up to 50 mention
     * {@code timestamps} ({@code {start, end}} seconds) for deep-linking; newest episodes
     * first. {@code entityType} ({@code null} to omit) is one of {@code person},
     * {@code organization}, {@code location}; {@code flyfId} ({@code null} to omit)
     * restricts to one podcast; {@code limit} default 20, max 100; {@code offset}
     * paginates (max 10000).
     */
    public Map<String, Object> getPodcastMentions(String entity, String entityType, String flyfId,
                                                  int limit, int offset) {
        return c.get("/audio/mentions", map("entity", entity, "entity_type", entityType,
                "flyf_id", flyfId, "limit", limit, "offset", offset));
    }

    /** Sponsor/ad placements for a company, newest first (limit 20). See the full overload. */
    public Map<String, Object> getPodcastSponsorsByCompany(String company) {
        return getPodcastSponsors(company, null, null, 20, 0);
    }

    /**
     * All ad placements in one episode, in ad order (limit 20). {@code episodeUrlHash} is
     * the SHA1 hex of the episode's full audio URL — use {@link #episodeUrlHash(String)}
     * to compute it. See the full overload.
     */
    public Map<String, Object> getPodcastSponsorsForEpisode(String episodeUrlHash) {
        return getPodcastSponsors(null, episodeUrlHash, null, 20, 0);
    }

    /**
     * All ad placements in one episode identified by its full audio URL, in ad order
     * (limit 20). The URL is hashed for you with {@link #episodeUrlHash(String)}. See the
     * full overload.
     */
    public Map<String, Object> getPodcastSponsorsForEpisodeUrl(String episodeUrl) {
        return getPodcastSponsorsForEpisodeUrl(episodeUrl, 20, 0);
    }

    /**
     * All ad placements in one episode identified by its full audio URL, in ad order.
     * The URL is hashed for you with {@link #episodeUrlHash(String)} and passed to
     * {@link #getPodcastSponsors} as {@code episode_url_hash}. {@code limit} default 20,
     * max 100; {@code offset} paginates (max 10000).
     *
     * @throws IllegalArgumentException when {@code episodeUrl} is null/empty
     */
    public Map<String, Object> getPodcastSponsorsForEpisodeUrl(String episodeUrl, int limit, int offset) {
        if (episodeUrl == null || episodeUrl.isEmpty()) {
            throw new IllegalArgumentException("episodeUrl is required");
        }
        return getPodcastSponsors(null, episodeUrlHash(episodeUrl), null, limit, offset);
    }

    /**
     * Query the podcast sponsor/ads database ({@code read:audio}). Each row is one
     * detected ad placement in one episode: advertiser, product, category, format, promo
     * code, exact time range, and an {@code ad_text_preview}. Search by {@code company}
     * (case-insensitive, newest placements first) or list all ads in a single episode with
     * {@code episodeUrlHash} (SHA1 hex of the full audio URL — see
     * {@link #episodeUrlHash(String)}); at least one of the two is required ({@code null}
     * to omit) — combine them to check whether a company advertised in a specific episode.
     * {@code flyfId} ({@code null} to omit) restricts to one podcast; {@code limit}
     * default 20, max 100; {@code offset} paginates (max 10000).
     *
     * @throws IllegalArgumentException when both {@code company} and
     *         {@code episodeUrlHash} are null/empty
     */
    public Map<String, Object> getPodcastSponsors(String company, String episodeUrlHash, String flyfId,
                                                  int limit, int offset) {
        if ((company == null || company.isEmpty())
                && (episodeUrlHash == null || episodeUrlHash.isEmpty())) {
            throw new IllegalArgumentException(
                    "provide at least one of company or episodeUrlHash");
        }
        return c.get("/audio/sponsors", map("company", company, "episode_url_hash", episodeUrlHash,
                "flyf_id", flyfId, "limit", limit, "offset", offset));
    }

    // Podcast intelligence — phase 4 (per-episode, retrieval only)

    /**
     * Stored fact-check results for an episode, in claim order ({@code read:audio}).
     * Each claim carries {@code claim_text}, {@code claim_type}, {@code timestamp_seconds},
     * a {@code verdict} with {@code confidence} and {@code explanation}, plus the
     * {@code sources} and {@code search_queries} behind it; the {@code summary} object
     * counts claims per verdict. Retrieval only — never triggers a new fact-check run.
     * Throws {@link SurfNotFoundError} when the episode has no fact checks.
     */
    public Map<String, Object> getFactChecks(String episodeUrl) {
        return c.get("/audio/fact-checks", map("episode_url", episodeUrl));
    }

    /**
     * A stored transcript translation for an episode in {@code language} (e.g. {@code "es"},
     * {@code "pt-BR"}; {@code read:audio}): the full {@code translated_transcript},
     * timestamped {@code translated_segments}, and — when TTS was generated — a translated
     * {@code audio_url} with duration and voice, under the {@code translation} key.
     * Retrieval only — never translates on demand. Throws {@link SurfNotFoundError} when
     * no stored translation exists for the language.
     */
    public Map<String, Object> getTranslation(String episodeUrl, String language) {
        return c.get("/audio/translations", map("episode_url", episodeUrl, "language", language));
    }

    /**
     * "What did I miss?" — summarizes an episode up to a playback position in seconds
     * (0-86400; {@code read:audio}): a prose {@code summary} plus {@code topics_covered},
     * {@code key_points}, and {@code missed_duration_seconds}. Works from the cached
     * transcript only and never triggers transcription — throws {@link SurfNotFoundError}
     * (error {@code "transcript not available"}) when the episode has no transcript yet.
     */
    public Map<String, Object> getCatchUp(String episodeUrl, double timestampSeconds) {
        return c.get("/audio/catch-up", map("episode_url", episodeUrl, "timestamp", timestampSeconds));
    }

    /** Skip-to-topic with the default match limit (5). See the full overload. */
    public Map<String, Object> skipToTopic(String episodeUrl, String topic) {
        return skipToTopic(episodeUrl, topic, 5);
    }

    /**
     * Semantic "jump to the part about X" within one episode ({@code read:audio}).
     * {@code matches} come back best first, each with {@code start_seconds}/{@code end_seconds}
     * for deep-linking, a {@code text_preview}, and a relevance {@code score}; an empty
     * {@code matches} list with {@code ok: true} means nothing scored above the relevance
     * floor. Works from the cached transcript only and never triggers transcription —
     * throws {@link SurfNotFoundError} when the episode has no transcript yet.
     * {@code limit} default 5, max 20.
     */
    public Map<String, Object> skipToTopic(String episodeUrl, String topic, int limit) {
        return c.get("/audio/skip-to-topic", map("episode_url", episodeUrl, "topic", topic,
                "limit", limit));
    }

    // Podcast popularity (daily charts)

    /** The US all-categories popular-shows chart with server defaults. See the full overload. */
    public Map<String, Object> getPopularShows() {
        return getPopularShows("us", "all", 50, true, null);
    }

    /**
     * Ranked popular podcast shows for one region/category daily snapshot
     * ({@code read:audio}). The chart blends Apple top charts, Podcast Index trending,
     * and Surf's fediverse engagement signal; rows come back in rank order and carry the
     * per-source ranks ({@code apple_rank}, {@code pi_trend_rank}) for "№ 3 on Apple"
     * style attribution, plus {@code flyf_id}/{@code feed_url} for feeding the other
     * audio APIs. {@code region} default {@code "us"}; {@code category} is {@code "all"}
     * or an Apple genre slug; {@code limit} default 50, max 200; {@code ingestedOnly}
     * true limits to shows already ingested and playable on Surf (false exposes the full
     * chart for gap analysis); {@code date} ({@code null} for the latest snapshot)
     * requests an explicit {@code YYYY-MM-DD} snapshot.
     */
    public Map<String, Object> getPopularShows(String region, String category, int limit,
                                               boolean ingestedOnly, String date) {
        return c.get("/audio/popular/shows", map("region", region, "category", category,
                "limit", limit, "ingestedOnly", ingestedOnly, "date", date));
    }

    /** The hot-episodes chart with server defaults. See the full overload. */
    public Map<String, Object> getPopularEpisodes() {
        return getPopularEpisodes(50, null);
    }

    /**
     * Ranked hot podcast episodes from the global daily snapshot ({@code read:audio}).
     * Episodes are ranked by fediverse engagement (favourites + reblogs + replies) and
     * mention breadth over a recent ingest window — a chart neither Apple nor Podcast
     * Index has. Rows come back in rank order, each with {@code episode_url} (the audio
     * file URL), {@code episode_url_hash}, {@code show_title}, {@code engagement_sum},
     * and {@code post_count}. {@code limit} default 50, max 200; {@code date}
     * ({@code null} for the latest snapshot) requests an explicit {@code YYYY-MM-DD}
     * snapshot.
     */
    public Map<String, Object> getPopularEpisodes(int limit, String date) {
        return c.get("/audio/popular/episodes", map("limit", limit, "date", date));
    }

    // Quiz

    /** Get the daily quiz questions. */
    public Map<String, Object> getDailyQuiz() {
        return c.get("/audio/quiz/daily");
    }

    // TTS

    /** Convert text to speech with the default voice ({@code write:audio}). Returns MP3 bytes. */
    public byte[] textToSpeech(String text) {
        return textToSpeech(text, "en-US-AriaNeural");
    }

    /** Convert text to speech ({@code write:audio}). Returns MP3 bytes. */
    public byte[] textToSpeech(String text, String voice) {
        return c.postBytes("/audio/tts", map("text", text, "voice", voice));
    }
}
