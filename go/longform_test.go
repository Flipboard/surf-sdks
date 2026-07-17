package surf

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"reflect"
	"strings"
	"testing"
)

// capturedAPIRequest records the fields of an incoming data-API request we
// assert on in the longform tests.
type capturedAPIRequest struct {
	method      string
	path        string     // r.URL.Path (net/http decodes percent-escapes)
	escapedPath string     // r.URL.EscapedPath() (percent-escapes preserved)
	query       url.Values // parsed query string
	apiKey      string
}

// newAPIServer returns an httptest server that records the last request it
// received into *capturedAPIRequest and responds with the given JSON body.
// The returned Client has its BaseURL pointed at the server (the SDK appends
// the /v1 prefix itself), so Longform/Search calls hit the test server with
// no network access and no real credentials.
func newAPIServer(t *testing.T, got *capturedAPIRequest, respBody string) *Client {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got.method = r.Method
		got.path = r.URL.Path
		got.escapedPath = r.URL.EscapedPath()
		got.query = r.URL.Query()
		got.apiKey = r.Header.Get("X-API-Key")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(respBody))
	}))
	t.Cleanup(srv.Close)
	c := NewClient("surf_sk_live_k")
	c.BaseURL = srv.URL
	return c
}

const testDocURI = "at://did:plc:x/site.standard.document/3k2a"

// escapedDocURI is testDocURI fully percent-encoded as a single path segment
// (encodeURIComponent semantics: both ':' and '/' encoded).
const escapedDocURI = "at%3A%2F%2Fdid%3Aplc%3Ax%2Fsite.standard.document%2F3k2a"

// TestLongformDocumentEscapesATURI proves the raw AT-URI travels as one fully
// percent-encoded path segment — ':' as %3A and '/' as %2F — and that the
// format parameter is omitted when no option is supplied.
func TestLongformDocumentEscapesATURI(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"id":"`+testDocURI+`","comments_count":0}`)
	if _, err := c.Longform.Document(testDocURI); err != nil {
		t.Fatalf("Document: %v", err)
	}
	if got.method != "GET" {
		t.Errorf("method = %q, want GET", got.method)
	}
	wantEscaped := "/v1/documents/" + escapedDocURI
	if got.escapedPath != wantEscaped {
		t.Errorf("escaped path = %q, want %q", got.escapedPath, wantEscaped)
	}
	// The decoded path must be the original AT-URI as a single segment.
	if got.path != "/v1/documents/"+testDocURI {
		t.Errorf("decoded path = %q, want %q", got.path, "/v1/documents/"+testDocURI)
	}
	if _, present := got.query["format"]; present {
		t.Errorf("format param sent without WithFormat: query = %v", got.query)
	}
}

// TestLongformDocumentFormat verifies WithFormat("blocks") is passed through
// as the format query parameter.
func TestLongformDocumentFormat(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"id":"x","comments_count":0,"pages":[]}`)
	if _, err := c.Longform.Document(testDocURI, WithFormat("blocks")); err != nil {
		t.Fatalf("Document: %v", err)
	}
	if f := got.query.Get("format"); f != "blocks" {
		t.Errorf("format = %q, want %q", f, "blocks")
	}
}

// TestLongformDocumentDecodes verifies the raw response decodes into the
// typed Document model.
func TestLongformDocumentDecodes(t *testing.T) {
	var got capturedAPIRequest
	body := `{"id":"` + testDocURI + `","title":"T","tags":["a"],"comments_count":3,` +
		`"publication":{"uri":"at://did:plc:x/site.standard.publication/1","name":"P"},` +
		`"author":{"did":"did:plc:x","handle":"h.example"},"content_html":"<p>hi</p>"}`
	c := newAPIServer(t, &got, body)
	raw, err := c.Longform.Document(testDocURI)
	if err != nil {
		t.Fatalf("Document: %v", err)
	}
	var doc Document
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("unmarshal Document: %v", err)
	}
	if doc.ID != testDocURI || doc.Title != "T" || doc.CommentsCount != 3 {
		t.Errorf("decoded Document = %+v", doc)
	}
	if doc.Publication == nil || doc.Publication.Name != "P" {
		t.Errorf("publication = %+v, want name P", doc.Publication)
	}
	if doc.Author == nil || doc.Author.DID != "did:plc:x" || doc.Author.Handle != "h.example" {
		t.Errorf("author = %+v", doc.Author)
	}
	if doc.ContentHTML != "<p>hi</p>" {
		t.Errorf("content_html = %q", doc.ContentHTML)
	}
}

// TestLongformPublicationEscapesATURI verifies the publication AT-URI is
// fully percent-encoded as a single path segment.
func TestLongformPublicationEscapesATURI(t *testing.T) {
	const pubURI = "at://did:plc:x/site.standard.publication/9z"
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{"uri":"`+pubURI+`","name":"P"}`)
	raw, err := c.Longform.Publication(pubURI)
	if err != nil {
		t.Fatalf("Publication: %v", err)
	}
	wantEscaped := "/v1/publications/at%3A%2F%2Fdid%3Aplc%3Ax%2Fsite.standard.publication%2F9z"
	if got.escapedPath != wantEscaped {
		t.Errorf("escaped path = %q, want %q", got.escapedPath, wantEscaped)
	}
	var pub Publication
	if err := json.Unmarshal(raw, &pub); err != nil {
		t.Fatalf("unmarshal Publication: %v", err)
	}
	if pub.URI != pubURI || pub.Name != "P" {
		t.Errorf("decoded Publication = %+v", pub)
	}
}

// TestLongformPublicationDocuments verifies the /documents sub-path, the
// repeatable tags parameter, and the count/from pagination parameters.
func TestLongformPublicationDocuments(t *testing.T) {
	const pubURI = "at://did:plc:x/site.standard.publication/9z"
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `[{"uri":"at://did:plc:x/site.standard.document/1","title":"A"}]`)
	raw, err := c.Longform.PublicationDocuments(pubURI,
		WithTags("go", "sdk"), WithCount(50), WithFrom(40))
	if err != nil {
		t.Fatalf("PublicationDocuments: %v", err)
	}
	wantEscaped := "/v1/publications/at%3A%2F%2Fdid%3Aplc%3Ax%2Fsite.standard.publication%2F9z/documents"
	if got.escapedPath != wantEscaped {
		t.Errorf("escaped path = %q, want %q", got.escapedPath, wantEscaped)
	}
	if tags := got.query["tags"]; !reflect.DeepEqual(tags, []string{"go", "sdk"}) {
		t.Errorf("tags = %v, want [go sdk]", tags)
	}
	if count := got.query.Get("count"); count != "50" {
		t.Errorf("count = %q, want 50", count)
	}
	if from := got.query.Get("from"); from != "40" {
		t.Errorf("from = %q, want 40", from)
	}
	var docs []PublicationDocument
	if err := json.Unmarshal(raw, &docs); err != nil {
		t.Fatalf("unmarshal []PublicationDocument: %v", err)
	}
	if len(docs) != 1 || docs[0].Title != "A" {
		t.Errorf("decoded docs = %+v", docs)
	}
}

// TestLongformPublicationDocumentsDefaults verifies tags/count/from are all
// omitted when no options are supplied.
func TestLongformPublicationDocumentsDefaults(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `[]`)
	if _, err := c.Longform.PublicationDocuments("at://did:plc:x/site.standard.publication/9z"); err != nil {
		t.Fatalf("PublicationDocuments: %v", err)
	}
	for _, key := range []string{"tags", "count", "from"} {
		if _, present := got.query[key]; present {
			t.Errorf("%s param sent without option: query = %v", key, got.query)
		}
	}
}

// TestLongformWithFromZero verifies WithFrom(0) is sent explicitly (it is an
// intentional offset, distinct from omitting the option).
func TestLongformWithFromZero(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `[]`)
	if _, err := c.Longform.SearchPublications("q", WithFrom(0)); err != nil {
		t.Fatalf("SearchPublications: %v", err)
	}
	if from := got.query.Get("from"); from != "0" {
		t.Errorf("from = %q, want 0", from)
	}
}

// TestLongformSearchPublications verifies the search path, required q, and
// count/from options.
func TestLongformSearchPublications(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `[{"uri":"at://did:plc:x/site.standard.publication/1","name":"P"}]`)
	raw, err := c.Longform.SearchPublications("climate", WithCount(10), WithFrom(20))
	if err != nil {
		t.Fatalf("SearchPublications: %v", err)
	}
	if got.path != "/v1/search/publications" {
		t.Errorf("path = %q, want /v1/search/publications", got.path)
	}
	if q := got.query.Get("q"); q != "climate" {
		t.Errorf("q = %q, want climate", q)
	}
	if count := got.query.Get("count"); count != "10" {
		t.Errorf("count = %q, want 10", count)
	}
	if from := got.query.Get("from"); from != "20" {
		t.Errorf("from = %q, want 20", from)
	}
	var pubs []Publication
	if err := json.Unmarshal(raw, &pubs); err != nil {
		t.Fatalf("unmarshal []Publication: %v", err)
	}
	if len(pubs) != 1 || pubs[0].Name != "P" {
		t.Errorf("decoded pubs = %+v", pubs)
	}
}

// TestSearchPublicationsIgnoresTags pins that an (unsupported) WithTags option
// never reaches the wire on /search/publications.
func TestSearchPublicationsIgnoresTags(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `[]`)
	if _, err := c.Longform.SearchPublications("climate", WithTags("a", "b"), WithCount(5)); err != nil {
		t.Fatalf("SearchPublications: %v", err)
	}
	if tags, present := got.query["tags"]; present {
		t.Errorf("tags param sent to /search/publications: %v", tags)
	}
	if count := got.query.Get("count"); count != "5" {
		t.Errorf("count = %q, want 5", count)
	}
}

// TestSearchPublicationsDelegates verifies Search.Publications hits the same
// endpoint as Longform.SearchPublications and forwards options.
func TestSearchPublicationsDelegates(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `[]`)
	if _, err := c.Search.Publications("news", WithCount(5)); err != nil {
		t.Fatalf("Search.Publications: %v", err)
	}
	if got.path != "/v1/search/publications" {
		t.Errorf("path = %q, want /v1/search/publications", got.path)
	}
	if q := got.query.Get("q"); q != "news" {
		t.Errorf("q = %q, want news", q)
	}
	if count := got.query.Get("count"); count != "5" {
		t.Errorf("count = %q, want 5", count)
	}
}

// TestLongformSendsAPIKey verifies the X-API-Key header carries the client's
// key on a longform call.
func TestLongformSendsAPIKey(t *testing.T) {
	var got capturedAPIRequest
	c := newAPIServer(t, &got, `{}`)
	if _, err := c.Longform.Publication(testDocURI); err != nil {
		t.Fatalf("Publication: %v", err)
	}
	if got.apiKey != "surf_sk_live_k" {
		t.Errorf("X-API-Key = %q, want %q", got.apiKey, "surf_sk_live_k")
	}
}

// TestEscapeATURI pins encodeURIComponent semantics for the escaper: ':' and
// '/' are encoded, unreserved characters pass through, and space is %20 (not
// the '+' that url.QueryEscape alone would emit).
func TestEscapeATURI(t *testing.T) {
	tests := []struct{ in, want string }{
		{testDocURI, escapedDocURI},
		{"a b", "a%20b"},
		{"plain-id_1.2~x", "plain-id_1.2~x"},
	}
	for _, tc := range tests {
		if got := escapeATURI(tc.in); got != tc.want {
			t.Errorf("escapeATURI(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
	if strings.Contains(escapeATURI(testDocURI), "/") {
		t.Error("escaped AT-URI still contains a raw '/'")
	}
}

// TestPostDocumentField verifies a Post decodes the optional longform
// document summary.
func TestPostDocumentField(t *testing.T) {
	raw := `{"id":"1","content":"c","created_at":"2026-07-17T00:00:00Z","url":"u",` +
		`"favourites_count":0,"reblogs_count":0,"replies_count":0,"visibility":"public","sensitive":false,` +
		`"document":{"title":"Doc","cover_image_url":"https://x/img.png","tags":["t1"],` +
		`"publication_uri":"at://did:plc:x/site.standard.publication/1"}}`
	var post Post
	if err := json.Unmarshal([]byte(raw), &post); err != nil {
		t.Fatalf("unmarshal Post: %v", err)
	}
	if post.Document == nil {
		t.Fatal("post.Document = nil, want summary")
	}
	if post.Document.Title != "Doc" || post.Document.PublicationURI != "at://did:plc:x/site.standard.publication/1" {
		t.Errorf("post.Document = %+v", post.Document)
	}
	// Absent document stays nil.
	var bare Post
	if err := json.Unmarshal([]byte(`{"id":"2"}`), &bare); err != nil {
		t.Fatalf("unmarshal bare Post: %v", err)
	}
	if bare.Document != nil {
		t.Errorf("bare post.Document = %+v, want nil", bare.Document)
	}
}
