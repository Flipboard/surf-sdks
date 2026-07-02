package surf

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// capturedRequest records the fields of an incoming request we assert on.
type capturedRequest struct {
	method      string
	path        string // r.URL.Path (net/http decodes percent-escapes)
	escapedPath string // r.URL.EscapedPath() (percent-escapes preserved)
	apiKey      string
	body        []byte
}

// newDiagServer returns an httptest server that records the last request it
// received into *capturedRequest and always responds with an empty JSON object.
// The returned Client is pointed at the server via WithDevportalURL, so the
// Diagnostics API (which targets DevportalURL) hits the test server with no
// network access and no real credentials.
func newDiagServer(t *testing.T, got *capturedRequest) *Client {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		got.method = r.Method
		got.path = r.URL.Path
		got.escapedPath = r.URL.EscapedPath()
		got.apiKey = r.Header.Get("X-API-Key")
		got.body = body
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{}`))
	}))
	t.Cleanup(srv.Close)
	return NewClient("surf_sk_live_k", WithDevportalURL(srv.URL))
}

func TestDiagnose(t *testing.T) {
	tests := []struct {
		name     string
		appID    string
		wantPath string // decoded r.URL.Path
	}{
		{"no app id", "", "/diagnose"},
		{"simple app id", "app1", "/applications/app1/diagnose"},
		{"app id with slash and space", "weird/id space", "/applications/weird/id space/diagnose"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			var got capturedRequest
			c := newDiagServer(t, &got)
			if _, err := c.Diagnostics.Diagnose(tc.appID); err != nil {
				t.Fatalf("Diagnose(%q): %v", tc.appID, err)
			}
			if got.method != "GET" {
				t.Errorf("method = %q, want GET", got.method)
			}
			if got.path != tc.wantPath {
				t.Errorf("path = %q, want %q", got.path, tc.wantPath)
			}
		})
	}
}

// TestDiagnoseEscapesSegment proves the app-id segment is percent-escaped on the
// wire (so a "/" in the id is not injected as an extra path segment). We assert
// on the escaped path, which preserves the encoding net/http would otherwise
// decode into r.URL.Path.
func TestDiagnoseEscapesSegment(t *testing.T) {
	var got capturedRequest
	c := newDiagServer(t, &got)
	if _, err := c.Diagnostics.Diagnose("weird/id space"); err != nil {
		t.Fatalf("Diagnose: %v", err)
	}
	if !strings.Contains(got.escapedPath, "weird%2Fid%20space") {
		t.Errorf("escaped path = %q, want it to contain %q", got.escapedPath, "weird%2Fid%20space")
	}
}

func TestCreateBundle(t *testing.T) {
	var got capturedRequest
	c := newDiagServer(t, &got)
	if _, err := c.Diagnostics.CreateBundle("app1", 5); err != nil {
		t.Fatalf("CreateBundle: %v", err)
	}
	if got.method != "POST" {
		t.Errorf("method = %q, want POST", got.method)
	}
	if got.path != "/applications/app1/debug-bundle" {
		t.Errorf("path = %q, want %q", got.path, "/applications/app1/debug-bundle")
	}
	var body struct {
		TTLMinutes int `json:"ttl_minutes"`
	}
	if err := json.Unmarshal(got.body, &body); err != nil {
		t.Fatalf("unmarshal body %q: %v", got.body, err)
	}
	if body.TTLMinutes != 5 {
		t.Errorf("ttl_minutes = %d, want 5", body.TTLMinutes)
	}
}

func TestGetBundle(t *testing.T) {
	var got capturedRequest
	c := newDiagServer(t, &got)
	if _, err := c.Diagnostics.GetBundle("dbg_a/b"); err != nil {
		t.Fatalf("GetBundle: %v", err)
	}
	if got.method != "GET" {
		t.Errorf("method = %q, want GET", got.method)
	}
	if !strings.Contains(got.escapedPath, "dbg_a%2Fb") {
		t.Errorf("escaped path = %q, want it to contain %q", got.escapedPath, "dbg_a%2Fb")
	}
}

func TestRevokeBundle(t *testing.T) {
	var got capturedRequest
	c := newDiagServer(t, &got)
	if _, err := c.Diagnostics.RevokeBundle("dbg_a/b"); err != nil {
		t.Fatalf("RevokeBundle: %v", err)
	}
	if got.method != "DELETE" {
		t.Errorf("method = %q, want DELETE", got.method)
	}
	if !strings.Contains(got.escapedPath, "dbg_a%2Fb") {
		t.Errorf("escaped path = %q, want it to contain %q", got.escapedPath, "dbg_a%2Fb")
	}
}

// TestDiagnosticsSendsAPIKey verifies the X-API-Key header carries the client's
// key on a diagnostics call.
func TestDiagnosticsSendsAPIKey(t *testing.T) {
	var got capturedRequest
	c := newDiagServer(t, &got)
	if _, err := c.Diagnostics.Diagnose(""); err != nil {
		t.Fatalf("Diagnose: %v", err)
	}
	if got.apiKey != "surf_sk_live_k" {
		t.Errorf("X-API-Key = %q, want %q", got.apiKey, "surf_sk_live_k")
	}
}

// TestDefaultDevportalURL pins the default developer-portal base URL so the
// Diagnostics API targets the right host when WithDevportalURL is not supplied.
func TestDefaultDevportalURL(t *testing.T) {
	const want = "https://surf.social/devportal/v1"
	if got := NewClient("k").DevportalURL; got != want {
		t.Errorf("DevportalURL = %q, want %q", got, want)
	}
}
