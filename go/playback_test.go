package surf

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

// Unit tests for the Playback namespace — no live API required. An httptest
// server stands in for api.surf.social and records what the SDK sends.

type playbackCall struct {
	method, rawPath, query string
	body                   []byte
}

func newPlaybackServer(t *testing.T, responses ...string) (*Client, *[]playbackCall) {
	t.Helper()
	calls := &[]playbackCall{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		*calls = append(*calls, playbackCall{r.Method, r.URL.EscapedPath(), r.URL.RawQuery, body})
		w.Header().Set("Content-Type", "application/json")
		if r.Method == "POST" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		resp := "[]"
		if n := len(*calls) - 1; n < len(responses) {
			resp = responses[n]
		}
		_, _ = w.Write([]byte(resp))
	}))
	t.Cleanup(srv.Close)
	c := NewClient("surf_sk_live_k")
	c.BaseURL = srv.URL
	return c, calls
}

func int64p(v int64) *int64 { return &v }
func boolp(v bool) *bool    { return &v }

func TestPlaybackReportSendsOnlyWhatItWasGiven(t *testing.T) {
	c, calls := newPlaybackServer(t)
	if err := c.Playback.Report(PlaybackReport{
		PostID: "p1", FeedSurfID: "surf/podcast/abc", PositionMs: 125000,
	}); err != nil {
		t.Fatal(err)
	}
	got := (*calls)[0]
	if got.method != "POST" || got.rawPath != "/v1/playback" {
		t.Fatalf("method/path = %s %s", got.method, got.rawPath)
	}
	var body map[string]interface{}
	if err := json.Unmarshal(got.body, &body); err != nil {
		t.Fatal(err)
	}
	// An omitted duration must be ABSENT, not 0: the server leaves a known
	// duration alone when a report omits it, and 0 would claim no length.
	if _, ok := body["duration_ms"]; ok {
		t.Error("duration_ms should be omitted when not given")
	}
	if _, ok := body["completed"]; ok {
		t.Error("completed should be omitted when not given")
	}
	if body["position_ms"].(float64) != 125000 {
		t.Errorf("position_ms = %v", body["position_ms"])
	}
}

func TestPlaybackReportSendsAZeroPositionBecauseZeroIsReal(t *testing.T) {
	c, calls := newPlaybackServer(t)
	if err := c.Playback.Report(PlaybackReport{
		PostID: "p1", FeedSurfID: "surf/podcast/abc", PositionMs: 0,
	}); err != nil {
		t.Fatal(err)
	}
	var body map[string]interface{}
	_ = json.Unmarshal((*calls)[0].body, &body)
	if v, ok := body["position_ms"]; !ok || v.(float64) != 0 {
		t.Errorf("a zero position must still be sent, got %v (present=%v)", v, ok)
	}
}

func TestPlaybackReportSendsCompletedFalseExplicitly(t *testing.T) {
	// False is a statement, not an omission: it is how a client says the
	// episode is not finished. The pointer is what makes the two expressible.
	c, calls := newPlaybackServer(t)
	if err := c.Playback.Report(PlaybackReport{
		PostID: "p1", FeedSurfID: "surf/podcast/abc", PositionMs: 1,
		Completed: boolp(false), DurationMs: int64p(3600000),
	}); err != nil {
		t.Fatal(err)
	}
	var body map[string]interface{}
	_ = json.Unmarshal((*calls)[0].body, &body)
	if v, ok := body["completed"]; !ok || v.(bool) {
		t.Errorf("completed should be present and false, got %v (present=%v)", v, ok)
	}
	if body["duration_ms"].(float64) != 3600000 {
		t.Errorf("duration_ms = %v", body["duration_ms"])
	}
}

func TestPlaybackBatchWrapsItems(t *testing.T) {
	c, calls := newPlaybackServer(t)
	if err := c.Playback.ReportBatch([]PlaybackReport{
		{PostID: "p1", FeedSurfID: "surf/podcast/abc", PositionMs: 10},
		{PostID: "p2", FeedSurfID: "surf/podcast/abc", PositionMs: 20},
	}); err != nil {
		t.Fatal(err)
	}
	got := (*calls)[0]
	if got.rawPath != "/v1/playback/batch" {
		t.Fatalf("path = %s", got.rawPath)
	}
	var body struct {
		Items []map[string]interface{} `json:"items"`
	}
	if err := json.Unmarshal(got.body, &body); err != nil {
		t.Fatal(err)
	}
	if len(body.Items) != 2 || body.Items[1]["post_id"] != "p2" {
		t.Errorf("items = %v", body.Items)
	}
}

func TestPlaybackRecentOmitsLimitWhenNotSet(t *testing.T) {
	c, calls := newPlaybackServer(t)
	if _, err := c.Playback.Recent(0); err != nil {
		t.Fatal(err)
	}
	if q := (*calls)[0].query; q != "" {
		t.Errorf("limit should be omitted so the server default applies, got %q", q)
	}
	if _, err := c.Playback.Recent(10); err != nil {
		t.Fatal(err)
	}
	if q := (*calls)[1].query; q != "limit=10" {
		t.Errorf("query = %q", q)
	}
}

func TestPlaybackPositionsRepeatsTheParam(t *testing.T) {
	c, calls := newPlaybackServer(t)
	if _, err := c.Playback.Positions([]string{"a", "b"}); err != nil {
		t.Fatal(err)
	}
	if q := (*calls)[0].query; q != "post_id=a&post_id=b" {
		t.Errorf("query = %q", q)
	}
}

func TestPlaybackPositionsWithNothingToAskMakesNoCall(t *testing.T) {
	// A list screen with no ids should not cost a round trip, and an empty
	// post_id would be a 400 rather than an empty answer.
	c, calls := newPlaybackServer(t)
	out, err := c.Playback.Positions([]string{"", ""})
	if err != nil {
		t.Fatal(err)
	}
	if string(out) != "[]" {
		t.Errorf("out = %s", out)
	}
	if len(*calls) != 0 {
		t.Errorf("expected no request, got %d", len(*calls))
	}
}
