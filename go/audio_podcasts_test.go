package surf

import (
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"testing"
)

// Unit tests for the podcast intelligence audio methods — no live API.
// Reuses newAPIServer/capturedAPIRequest from longform_test.go.

const (
	testEpisodeURL = "https://cdn.example.com/podcasts/ep-142.mp3"
	testFlyfID     = "d7e340ff6462708b5519d65d3faab82ecb6c4c37"
)

func TestEpisodeURLHash(t *testing.T) {
	sum := sha1.Sum([]byte(testEpisodeURL))
	if got, want := EpisodeURLHash(testEpisodeURL), hex.EncodeToString(sum[:]); got != want {
		t.Fatalf("EpisodeURLHash = %q, want %q", got, want)
	}
	if got := EpisodeURLHash("abc"); got != "a9993e364706816aba3e25717850c26c9cd0d89d" {
		t.Fatalf("EpisodeURLHash(abc) = %q", got)
	}
}

func TestSearchPodcastEpisodes(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true,"query":"ai","total":0,"results":[]}`)
	raw, err := c.Audio.SearchPodcastEpisodes("ai agents", testFlyfID, 5)
	if err != nil {
		t.Fatalf("SearchPodcastEpisodes: %v", err)
	}
	if got.method != "GET" || got.path != "/v1/audio/episodes/search" {
		t.Fatalf("request = %s %s", got.method, got.path)
	}
	if got.query.Get("q") != "ai agents" || got.query.Get("flyf_id") != testFlyfID || got.query.Get("limit") != "5" {
		t.Fatalf("query = %v", got.query)
	}
	var resp PodcastEpisodeSearchResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if !resp.OK || resp.Query != "ai" {
		t.Fatalf("resp = %+v", resp)
	}
}

func TestSearchPodcastEpisodesOmitsOptionalParams(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	if _, err := c.Audio.SearchPodcastEpisodes("ai", "", 0); err != nil {
		t.Fatalf("SearchPodcastEpisodes: %v", err)
	}
	if _, ok := got.query["flyf_id"]; ok {
		t.Fatal("flyf_id should be omitted when empty")
	}
	if _, ok := got.query["limit"]; ok {
		t.Fatal("limit should be omitted when <= 0")
	}
}

func TestSearchPodcastGuests(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true,"query":"sam","guests":[],"total":0}`)
	if _, err := c.Audio.SearchPodcastGuests("Sam Altman", 3); err != nil {
		t.Fatalf("SearchPodcastGuests: %v", err)
	}
	if got.path != "/v1/audio/guests/search" {
		t.Fatalf("path = %s", got.path)
	}
	if got.query.Get("q") != "Sam Altman" || got.query.Get("limit") != "3" {
		t.Fatalf("query = %v", got.query)
	}
}

func TestGetPodcastMentions(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true,"entity":"anthropic","mentions":[],"total":0,"limit":50,"offset":100}`)
	if _, err := c.Audio.GetPodcastMentions("Anthropic", "organization", testFlyfID, 50, 100); err != nil {
		t.Fatalf("GetPodcastMentions: %v", err)
	}
	if got.path != "/v1/audio/mentions" {
		t.Fatalf("path = %s", got.path)
	}
	q := got.query
	if q.Get("entity") != "Anthropic" || q.Get("entity_type") != "organization" ||
		q.Get("flyf_id") != testFlyfID || q.Get("limit") != "50" || q.Get("offset") != "100" {
		t.Fatalf("query = %v", q)
	}
}

func TestGetPodcastMentionsMinimal(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	if _, err := c.Audio.GetPodcastMentions("Anthropic", "", "", 0, 0); err != nil {
		t.Fatalf("GetPodcastMentions: %v", err)
	}
	for _, k := range []string{"entity_type", "flyf_id", "limit", "offset"} {
		if _, ok := got.query[k]; ok {
			t.Fatalf("%s should be omitted", k)
		}
	}
}

func TestGetPodcastSponsorsByCompany(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true,"company":"squarespace","sponsors":[],"total":0,"limit":20,"offset":0}`)
	raw, err := c.Audio.GetPodcastSponsors("Squarespace", "", "", 0, 0)
	if err != nil {
		t.Fatalf("GetPodcastSponsors: %v", err)
	}
	if got.path != "/v1/audio/sponsors" || got.query.Get("company") != "Squarespace" {
		t.Fatalf("request = %s query=%v", got.path, got.query)
	}
	var resp PodcastSponsorsResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.Company == nil || *resp.Company != "squarespace" {
		t.Fatalf("resp = %+v", resp)
	}
}

func TestGetPodcastSponsorsByEpisode(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	hash := EpisodeURLHash(testEpisodeURL)
	if _, err := c.Audio.GetPodcastSponsors("", hash, "", 0, 0); err != nil {
		t.Fatalf("GetPodcastSponsors: %v", err)
	}
	if got.query.Get("episode_url_hash") != hash {
		t.Fatalf("query = %v", got.query)
	}
	if _, ok := got.query["company"]; ok {
		t.Fatal("company should be omitted when empty")
	}
}

func TestGetPodcastSponsorsRequiresCompanyOrEpisode(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	if _, err := c.Audio.GetPodcastSponsors("", "", testFlyfID, 20, 0); err == nil {
		t.Fatal("expected an error when neither company nor episodeURLHash is set")
	}
	if got.method != "" {
		t.Fatal("no request should be made")
	}
}

func TestGetShowNotes(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"status":"ready"}`)
	if _, err := c.Audio.GetShowNotes(testEpisodeURL, ""); err != nil {
		t.Fatalf("GetShowNotes: %v", err)
	}
	if got.path != "/v1/audio/transcripts/show-notes" || got.query.Get("episode_url") != testEpisodeURL {
		t.Fatalf("request = %s query=%v", got.path, got.query)
	}
	if _, ok := got.query["language"]; ok {
		t.Fatal("language should be omitted when empty")
	}

	if _, err := c.Audio.GetShowNotes(testEpisodeURL, "es"); err != nil {
		t.Fatalf("GetShowNotes(es): %v", err)
	}
	if got.query.Get("language") != "es" {
		t.Fatalf("query = %v", got.query)
	}
}

// ---------------------------------------------------------------------------
// Phase 4 — fact checks, translations, catch-up, skip-to-topic
// ---------------------------------------------------------------------------

func TestGetFactChecks(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true,"episode_url":"`+testEpisodeURL+`","fact_checks":[{"claim_index":0,"claim_text":"US inflation fell below 3 percent in 2025.","verdict":"verified","confidence":0.92}],"total":1,"summary":{"verified":1}}`)
	raw, err := c.Audio.GetFactChecks(testEpisodeURL)
	if err != nil {
		t.Fatalf("GetFactChecks: %v", err)
	}
	if got.method != "GET" || got.path != "/v1/audio/fact-checks" {
		t.Fatalf("request = %s %s", got.method, got.path)
	}
	if got.query.Get("episode_url") != testEpisodeURL {
		t.Fatalf("query = %v", got.query)
	}
	var resp PodcastFactChecksResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if !resp.OK || resp.Total != 1 || resp.FactChecks[0].Verdict != "verified" {
		t.Fatalf("resp = %+v", resp)
	}
	if resp.Summary["verified"] != 1 {
		t.Fatalf("summary = %+v", resp.Summary)
	}
}

func TestGetTranslation(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true,"episode_url":"`+testEpisodeURL+`","language":"es","translation":{"source_language":"en","target_language":"es","translated_transcript":"Bienvenidos","word_count":9421}}`)
	raw, err := c.Audio.GetTranslation(testEpisodeURL, "es")
	if err != nil {
		t.Fatalf("GetTranslation: %v", err)
	}
	if got.path != "/v1/audio/translations" {
		t.Fatalf("path = %s", got.path)
	}
	if got.query.Get("episode_url") != testEpisodeURL || got.query.Get("language") != "es" {
		t.Fatalf("query = %v", got.query)
	}
	var resp PodcastTranslationResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.Translation == nil || resp.Translation.TranslatedTranscript != "Bienvenidos" {
		t.Fatalf("resp = %+v", resp)
	}
	if resp.Translation.WordCount == nil || *resp.Translation.WordCount != 9421 {
		t.Fatalf("word_count = %+v", resp.Translation.WordCount)
	}
}

func TestGetTranslationRegionalLanguageCode(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	if _, err := c.Audio.GetTranslation(testEpisodeURL, "pt-BR"); err != nil {
		t.Fatalf("GetTranslation: %v", err)
	}
	if got.query.Get("language") != "pt-BR" {
		t.Fatalf("query = %v", got.query)
	}
}

func TestGetCatchUp(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true,"episode_url":"`+testEpisodeURL+`","timestamp_seconds":1830.5,"summary":"The hosts opened with the news.","topics_covered":["AI"],"key_points":["evals"],"missed_duration_seconds":1830.5}`)
	raw, err := c.Audio.GetCatchUp(testEpisodeURL, 1830.5)
	if err != nil {
		t.Fatalf("GetCatchUp: %v", err)
	}
	if got.path != "/v1/audio/catch-up" {
		t.Fatalf("path = %s", got.path)
	}
	if got.query.Get("episode_url") != testEpisodeURL || got.query.Get("timestamp") != "1830.5" {
		t.Fatalf("query = %v", got.query)
	}
	var resp PodcastCatchUpResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if !resp.OK || resp.TimestampSeconds != 1830.5 || len(resp.TopicsCovered) != 1 {
		t.Fatalf("resp = %+v", resp)
	}
}

func TestGetCatchUpZeroTimestampSent(t *testing.T) {
	// 0 is a valid playback position and must be sent, not omitted.
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	if _, err := c.Audio.GetCatchUp(testEpisodeURL, 0); err != nil {
		t.Fatalf("GetCatchUp: %v", err)
	}
	if got.query.Get("timestamp") != "0" {
		t.Fatalf("query = %v", got.query)
	}
}

func TestSkipToTopic(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true,"episode_url":"`+testEpisodeURL+`","topic":"the housing market","matches":[{"start_seconds":2105.3,"end_seconds":2189.9,"text_preview":"housing prices cooled","score":0.78}],"total":1}`)
	raw, err := c.Audio.SkipToTopic(testEpisodeURL, "the housing market", 20)
	if err != nil {
		t.Fatalf("SkipToTopic: %v", err)
	}
	if got.path != "/v1/audio/skip-to-topic" {
		t.Fatalf("path = %s", got.path)
	}
	q := got.query
	if q.Get("episode_url") != testEpisodeURL || q.Get("topic") != "the housing market" || q.Get("limit") != "20" {
		t.Fatalf("query = %v", q)
	}
	var resp PodcastTopicSeekResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if !resp.OK || resp.Total != 1 || resp.Matches[0].Score == nil || *resp.Matches[0].Score != 0.78 {
		t.Fatalf("resp = %+v", resp)
	}
}

func TestSkipToTopicOmitsLimitWhenZero(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	if _, err := c.Audio.SkipToTopic(testEpisodeURL, "evals", 0); err != nil {
		t.Fatalf("SkipToTopic: %v", err)
	}
	if _, ok := got.query["limit"]; ok {
		t.Fatal("limit should be omitted when <= 0 (server default 5)")
	}
}
