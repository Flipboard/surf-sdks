package social.surf.api;

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
