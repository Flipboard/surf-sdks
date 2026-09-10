package surf

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

// Unit tests for the Sonars namespace — no live API required. An httptest
// server stands in for api.surf.social and records what the SDK sends: method,
// path (raw, so escaping is visible), query and body.

type sonarCall struct {
	method, rawPath, query string
	body                   []byte
}

func newSonarServer(t *testing.T, responses ...string) (*Client, *[]sonarCall) {
	t.Helper()
	calls := &[]sonarCall{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		*calls = append(*calls, sonarCall{r.Method, r.URL.EscapedPath(), r.URL.RawQuery, body})
		w.Header().Set("Content-Type", "application/json")
		if r.Method == "DELETE" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		resp := "{}"
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

var sonarSpec = SonarSpec{Subject: SonarSubject{Hashtags: []string{"#opensearch"}}, Surfaces: []string{"bluesky", "mastodon"}}

func TestSonarsCreateSendsNameSpecAndOnlyGivenDeliveryFields(t *testing.T) {
	c, calls := newSonarServer(t)
	if _, err := c.Sonars.Create(SonarRequest{Name: "OpenSearch chatter", Spec: &sonarSpec}); err != nil {
		t.Fatal(err)
	}
	got := (*calls)[0]
	if got.method != "POST" || got.rawPath != "/v1/sonars" {
		t.Errorf("got %s %s, want POST /v1/sonars", got.method, got.rawPath)
	}
	var body map[string]interface{}
	_ = json.Unmarshal(got.body, &body)
	if body["name"] != "OpenSearch chatter" || body["spec"] == nil {
		t.Errorf("body = %s", got.body)
	}
	for _, k := range []string{"enabled", "cadence", "channels", "daily_cap"} {
		if _, present := body[k]; present {
			t.Errorf("%s should be omitted when unset: %s", k, got.body)
		}
	}
	cap := 20
	enabled := false
	if _, err := c.Sonars.Create(SonarRequest{Name: "n", Spec: &sonarSpec, Enabled: &enabled, Cadence: "instant",
		Channels: []SonarChannel{{Type: "push"}}, DailyCap: &cap}); err != nil {
		t.Fatal(err)
	}
	if string((*calls)[1].body) != `{"name":"n","spec":{"subject":{"hashtags":["#opensearch"]},"surfaces":["bluesky","mastodon"]},"enabled":false,"cadence":"instant","channels":[{"type":"push"}],"daily_cap":20}` {
		t.Errorf("full body = %s", (*calls)[1].body)
	}
}

func TestSonarsListGetDeletePathsAndEscaping(t *testing.T) {
	c, calls := newSonarServer(t)
	if _, err := c.Sonars.List(); err != nil {
		t.Fatal(err)
	}
	if _, err := c.Sonars.Get("01j0ksyw6tgwfs0zmhhbc42kwa"); err != nil {
		t.Fatal(err)
	}
	if _, err := c.Sonars.Get("odd/id"); err != nil {
		t.Fatal(err)
	}
	if err := c.Sonars.Delete("abc"); err != nil {
		t.Fatalf("Delete on 204: %v", err)
	}
	want := []struct{ method, path string }{
		{"GET", "/v1/sonars"}, {"GET", "/v1/sonars/01j0ksyw6tgwfs0zmhhbc42kwa"}, {"GET", "/v1/sonars/odd%2Fid"}, {"DELETE", "/v1/sonars/abc"},
	}
	for i, w := range want {
		if (*calls)[i].method != w.method || (*calls)[i].rawPath != w.path {
			t.Errorf("call %d = %s %s, want %s %s", i, (*calls)[i].method, (*calls)[i].rawPath, w.method, w.path)
		}
	}
}

func TestSonarsUpdatePatchesOnlyGivenFieldsAndCanClearTheCap(t *testing.T) {
	c, calls := newSonarServer(t)
	if _, err := c.Sonars.Update("abc", SonarRequest{Name: "renamed"}); err != nil {
		t.Fatal(err)
	}
	if (*calls)[0].method != "PATCH" || (*calls)[0].rawPath != "/v1/sonars/abc" || string((*calls)[0].body) != `{"name":"renamed"}` {
		t.Errorf("got %s %s %s", (*calls)[0].method, (*calls)[0].rawPath, (*calls)[0].body)
	}
	// clearing needs an explicit null, which omitempty cannot express: use a map
	if _, err := c.Sonars.Update("abc", map[string]interface{}{"daily_cap": nil, "enabled": false}); err != nil {
		t.Fatal(err)
	}
	if string((*calls)[1].body) != `{"daily_cap":null,"enabled":false}` {
		t.Errorf("clear body = %s", (*calls)[1].body)
	}
}

func TestSonarsMatchesAndPreviewParams(t *testing.T) {
	c, calls := newSonarServer(t,
		`{"matches":[{"id":3,"sonar_id":"abc","post_id":"p3","matched_at":"2026-09-10T00:00:00Z","why":{"matched_by":"hashtag"},"delivered":true}],"next_before":3}`,
		`{}`,
		`{"window_days":7,"total":42,"per_day":[{"day":"2026-09-09T00:00:00.000Z","count":42}],"samples":[{"id":"x","service":"bluesky"}]}`,
	)
	raw, err := c.Sonars.Matches("abc", 0, 0)
	if err != nil {
		t.Fatal(err)
	}
	if (*calls)[0].rawPath != "/v1/sonars/abc/matches" || (*calls)[0].query != "" {
		t.Errorf("first page: %s ? %s", (*calls)[0].rawPath, (*calls)[0].query)
	}
	var page SonarMatchPage
	if err := json.Unmarshal(raw, &page); err != nil {
		t.Fatal(err)
	}
	if len(page.Matches) != 1 || page.Matches[0].PostID != "p3" || !page.Matches[0].Delivered || page.NextBefore == nil || *page.NextBefore != 3 {
		t.Errorf("page = %+v", page)
	}
	if _, err := c.Sonars.Matches("abc", *page.NextBefore, 10); err != nil {
		t.Fatal(err)
	}
	if (*calls)[1].query != "before=3&limit=10" {
		t.Errorf("second page query = %s", (*calls)[1].query)
	}

	raw, err = c.Sonars.Preview(sonarSpec, 7)
	if err != nil {
		t.Fatal(err)
	}
	if (*calls)[2].method != "POST" || (*calls)[2].rawPath != "/v1/sonars/preview" || (*calls)[2].query != "days=7" {
		t.Errorf("preview: %s %s ? %s", (*calls)[2].method, (*calls)[2].rawPath, (*calls)[2].query)
	}
	if string((*calls)[2].body) != `{"subject":{"hashtags":["#opensearch"]},"surfaces":["bluesky","mastodon"]}` {
		t.Errorf("preview body = %s", (*calls)[2].body)
	}
	var preview SonarPreview
	if err := json.Unmarshal(raw, &preview); err != nil {
		t.Fatal(err)
	}
	if preview.WindowDays != 7 || preview.Total != 42 || len(preview.PerDay) != 1 || preview.Samples[0].Service == nil || *preview.Samples[0].Service != "bluesky" {
		t.Errorf("preview = %+v", preview)
	}
	if _, err := c.Sonars.Preview(sonarSpec, 0); err != nil {
		t.Fatal(err)
	}
	if (*calls)[3].query != "" {
		t.Errorf("days <= 0 should omit the param, got %q", (*calls)[3].query)
	}
}

func TestSonarDecodesTheWireShape(t *testing.T) {
	var s Sonar
	err := json.Unmarshal([]byte(`{"id":"abc","owner_id":"o","name":"n","enabled":true,
		"spec":{"subject":{"hashtags":["#opensearch"]},"surfaces":["bluesky"]},"cadence":"instant",
		"channels":[{"type":"push"}],"daily_cap":null,"tier":"free","created":"2026-09-10T00:00:00Z","updated":"2026-09-10T00:00:00Z"}`), &s)
	if err != nil {
		t.Fatal(err)
	}
	if s.ID != "abc" || s.Spec.Subject.Hashtags[0] != "#opensearch" || s.Channels[0].Type != "push" || s.DailyCap != nil || s.Tier == nil || *s.Tier != "free" {
		t.Errorf("sonar = %+v", s)
	}
}
