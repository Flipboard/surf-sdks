package surf

import (
	"net/http"
	"testing"
)

// A client must hold exactly one credential. Both set would silently pick one and could make
// calls act as the wrong principal; neither set would send an empty key and fail every call.
func TestNewClientRequiresExactlyOneCredential(t *testing.T) {
	cases := []struct {
		name      string
		apiKey    string
		opts      []ClientOption
		wantPanic bool
	}{
		{"api key only", "surf_sk_live_x", nil, false},
		{"access token only", "", []ClientOption{WithAccessToken("jwt")}, false},
		{"both", "surf_sk_live_x", []ClientOption{WithAccessToken("jwt")}, true},
		{"neither", "", nil, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			defer func() {
				if r := recover(); (r != nil) != tc.wantPanic {
					t.Errorf("panic=%v, want %v (%v)", r != nil, tc.wantPanic, r)
				}
			}()
			NewClient(tc.apiKey, tc.opts...)
		})
	}
}

func TestSetAuthPicksTheRightHeader(t *testing.T) {
	oauth := NewClient("", WithAccessToken("jwt-token"))
	req := newBlankRequest(t)
	oauth.setAuth(req)
	if got := req.Header.Get("Authorization"); got != "Bearer jwt-token" {
		t.Errorf("Authorization = %q, want %q", got, "Bearer jwt-token")
	}
	if got := req.Header.Get("X-API-Key"); got != "" {
		t.Errorf("X-API-Key = %q, want empty for an OAuth client", got)
	}

	app := NewClient("surf_sk_live_x")
	req = newBlankRequest(t)
	app.setAuth(req)
	if got := req.Header.Get("X-API-Key"); got != "surf_sk_live_x" {
		t.Errorf("X-API-Key = %q, want the app key", got)
	}
	if got := req.Header.Get("Authorization"); got != "" {
		t.Errorf("Authorization = %q, want empty for an app-key client", got)
	}
}

func newBlankRequest(t *testing.T) *http.Request {
	t.Helper()
	req, err := http.NewRequest("GET", "https://api.surf.social/v1/feed", nil)
	if err != nil {
		t.Fatalf("building request: %v", err)
	}
	return req
}
