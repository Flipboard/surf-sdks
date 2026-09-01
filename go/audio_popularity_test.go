package surf

import (
	"encoding/json"
	"testing"
)

// Unit tests for the podcast popularity audio methods — no live API.
// Reuses newAPIServer/capturedAPIRequest from longform_test.go.

func TestGetPopularShows(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{
		"ok": true, "region": "gb", "category": "technology",
		"snapshot_date": "2026-08-31", "ingested_only": false, "limit": 10,
		"shows": [{
			"rank": 1, "score": 97.4,
			"flyf_id": "d7e340ff6462708b5519d65d3faab82ecb6c4c37",
			"ingested": true, "feed_url": "https://feeds.example.com/acquired.rss",
			"title": "Acquired", "artwork_url": "https://cdn.example.com/a.jpg",
			"itunes_id": 1050462261, "podcastindex_id": 217134,
			"apple_rank": 3, "pi_trend_rank": 7, "engagement_7d": 4211,
			"created_at": "2026-08-31T06:00:00Z"
		}],
		"total": 1
	}`)
	raw, err := c.Audio.GetPopularShows("gb", "technology", 10, false, "2026-08-30")
	if err != nil {
		t.Fatalf("GetPopularShows: %v", err)
	}
	if got.method != "GET" || got.path != "/v1/audio/popular/shows" {
		t.Fatalf("request = %s %s", got.method, got.path)
	}
	if got.query.Get("region") != "gb" || got.query.Get("category") != "technology" {
		t.Fatalf("query = %v", got.query)
	}
	if got.query.Get("limit") != "10" || got.query.Get("ingestedOnly") != "false" || got.query.Get("date") != "2026-08-30" {
		t.Fatalf("query = %v", got.query)
	}
	var resp PopularShowsResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if !resp.OK || resp.Region != "gb" || resp.Total != 1 || len(resp.Shows) != 1 {
		t.Fatalf("resp = %+v", resp)
	}
	s := resp.Shows[0]
	if s.Rank != 1 || !s.Ingested || s.AppleRank == nil || *s.AppleRank != 3 {
		t.Fatalf("show = %+v", s)
	}
	if s.PITrendRank == nil || *s.PITrendRank != 7 || s.Engagement7d == nil || *s.Engagement7d != 4211 {
		t.Fatalf("show = %+v", s)
	}
	if s.PodcastIndexID == nil || *s.PodcastIndexID != 217134 {
		t.Fatalf("show = %+v", s)
	}
}

func TestGetPopularShowsOmitsOptionalParams(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	if _, err := c.Audio.GetPopularShows("", "", 0, true, ""); err != nil {
		t.Fatalf("GetPopularShows: %v", err)
	}
	for _, k := range []string{"region", "category", "limit", "date"} {
		if _, ok := got.query[k]; ok {
			t.Fatalf("%s should be omitted when zero-valued", k)
		}
	}
	// ingestedOnly is always sent explicitly.
	if got.query.Get("ingestedOnly") != "true" {
		t.Fatalf("ingestedOnly = %q, want true", got.query.Get("ingestedOnly"))
	}
}

func TestGetPopularEpisodes(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{
		"ok": true, "snapshot_date": "2026-08-31", "limit": 5,
		"episodes": [{
			"rank": 1, "score": 88.2,
			"episode_url_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
			"episode_url": "https://cdn.example.com/podcasts/ep-142.mp3",
			"flyf_id": "d7e340ff6462708b5519d65d3faab82ecb6c4c37",
			"title": "Nvidia part III", "show_title": "Acquired",
			"artwork_url": "https://cdn.example.com/a.jpg",
			"engagement_sum": 913, "post_count": 57,
			"created_at": "2026-08-31T06:00:00Z"
		}],
		"total": 1
	}`)
	raw, err := c.Audio.GetPopularEpisodes(5, "2026-08-30")
	if err != nil {
		t.Fatalf("GetPopularEpisodes: %v", err)
	}
	if got.method != "GET" || got.path != "/v1/audio/popular/episodes" {
		t.Fatalf("request = %s %s", got.method, got.path)
	}
	if got.query.Get("limit") != "5" || got.query.Get("date") != "2026-08-30" {
		t.Fatalf("query = %v", got.query)
	}
	var resp PopularEpisodesResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if !resp.OK || resp.Total != 1 || len(resp.Episodes) != 1 {
		t.Fatalf("resp = %+v", resp)
	}
	e := resp.Episodes[0]
	if e.Rank != 1 || e.EpisodeURL != "https://cdn.example.com/podcasts/ep-142.mp3" {
		t.Fatalf("episode = %+v", e)
	}
	if e.EngagementSum != 913 || e.PostCount != 57 || e.ShowTitle == nil || *e.ShowTitle != "Acquired" {
		t.Fatalf("episode = %+v", e)
	}
}

func TestGetPopularEpisodesOmitsOptionalParams(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"ok":true}`)
	if _, err := c.Audio.GetPopularEpisodes(0, ""); err != nil {
		t.Fatalf("GetPopularEpisodes: %v", err)
	}
	if _, ok := got.query["limit"]; ok {
		t.Fatal("limit should be omitted when <= 0")
	}
	if _, ok := got.query["date"]; ok {
		t.Fatal("date should be omitted when empty")
	}
}
