// Package surf provides a Go client for the Surf social platform API.
//
// Usage:
//
//	client := surf.NewClient("surf_sk_live_your_token_here")
//	feed, err := client.Feeds.Get("surf/topic/technology")
//	posts, err := client.Feeds.GetPosts("surf/topic/technology", &surf.PostsOptions{Limit: 20})
//	summary, err := client.AI.FeedSummary("surf/topic/technology", 20)
package surf

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

const (
	DefaultBaseURL = "https://api.surf.social"
	apiPrefix      = "/v1"
	userAgent      = "surf-api-go/1.0.0"
)

// Client is the Surf API client.
type Client struct {
	APIKey  string
	BaseURL string
	HTTP    *http.Client

	maxRetries int // set via WithMaxRetries option; default 3

	// Sub-clients
	Feeds         *FeedsAPI
	Search        *SearchAPI
	AI            *AIAPI
	Account       *AccountAPI
	Content       *ContentAPI
	Images        *ImagesAPI
	Audio         *AudioAPI
	Notifications *NotificationsAPI
	Preferences   *PreferencesAPI
	CustomFeeds   *CustomFeedsAPI
	Media         *MediaAPI

	// RateLimit is updated after each request.
	RateLimit *RateLimitInfo
}

// ClientOption configures a Client.
type ClientOption func(*Client)

// WithMaxRetries sets the number of retries after the initial attempt on 429,
// 5xx, or transient network errors (default 3; 0 disables retry).
func WithMaxRetries(n int) ClientOption {
	return func(c *Client) {
		if n >= 0 {
			c.maxRetries = n
		}
	}
}

// RateLimitInfo holds rate limit data from response headers.
type RateLimitInfo struct {
	Limit     int
	Remaining int
	Reset     string
}

// NewClient creates a new Surf API client. Pass ClientOption values to override defaults.
func NewClient(apiKey string, opts ...ClientOption) *Client {
	c := &Client{
		APIKey:     apiKey,
		BaseURL:    DefaultBaseURL,
		HTTP:       &http.Client{Timeout: 30 * time.Second},
		maxRetries: 3,
	}
	for _, opt := range opts {
		opt(c)
	}
	c.Feeds = &FeedsAPI{c: c}
	c.Search = &SearchAPI{c: c}
	c.AI = &AIAPI{c: c}
	c.Account = &AccountAPI{c: c}
	c.Content = &ContentAPI{c: c}
	c.Images = &ImagesAPI{c: c}
	c.Audio = &AudioAPI{c: c}
	c.Notifications = &NotificationsAPI{c: c}
	c.Preferences = &PreferencesAPI{c: c}
	c.CustomFeeds = &CustomFeedsAPI{c: c}
	c.Media = &MediaAPI{c: c}
	return c
}

// APIError is returned for non-2xx responses by both Client and RTBClient.
// StatusCode always carries the HTTP status (e.g. 401 unauthorized, 403
// missing scope, 429 rate limited), so callers can branch on it via errors.As:
//
//	var apiErr *surf.APIError
//	if errors.As(err, &apiErr) && apiErr.StatusCode == 403 { ... }
type APIError struct {
	StatusCode int
	ErrorCode  string `json:"error"`
	Message    string `json:"error_description"`
}

func (e *APIError) Error() string {
	return fmt.Sprintf("surf api: %d %s: %s", e.StatusCode, e.ErrorCode, e.Message)
}

func (c *Client) url(path string) string {
	return c.BaseURL + apiPrefix + path
}

func (c *Client) do(method, path string, params url.Values, body interface{}) ([]byte, error) {
	u := c.url(path)
	if params != nil && len(params) > 0 {
		u += "?" + params.Encode()
	}

	var bodyBytes []byte
	if body != nil {
		var err error
		bodyBytes, err = json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("surf: marshal body: %w", err)
		}
	}

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		var reqBody io.Reader
		if bodyBytes != nil {
			reqBody = bytes.NewReader(bodyBytes)
		}

		req, err := http.NewRequest(method, u, reqBody)
		if err != nil {
			return nil, err
		}
		req.Header.Set("X-API-Key", c.APIKey)
		req.Header.Set("User-Agent", userAgent)
		req.Header.Set("Accept", "application/json")
		if bodyBytes != nil {
			req.Header.Set("Content-Type", "application/json")
		}

		resp, err := c.HTTP.Do(req)
		if err != nil {
			if attempt < c.maxRetries {
				time.Sleep(cappedBackoff(attempt))
				continue
			}
			return nil, err
		}

		c.RateLimit = &RateLimitInfo{
			Limit:     atoi(resp.Header.Get("X-RateLimit-Limit")),
			Remaining: atoi(resp.Header.Get("X-RateLimit-Remaining")),
			Reset:     resp.Header.Get("X-RateLimit-Reset"),
		}

		data, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if readErr != nil {
			return nil, readErr
		}

		if resp.StatusCode == 429 && attempt < c.maxRetries {
			retryAfter := atoi(resp.Header.Get("Retry-After"))
			if retryAfter <= 0 {
				retryAfter = int(cappedBackoff(attempt).Seconds())
			}
			if retryAfter > 60 {
				retryAfter = 60
			}
			time.Sleep(time.Duration(retryAfter) * time.Second)
			continue
		}

		if resp.StatusCode >= 500 && attempt < c.maxRetries {
			time.Sleep(cappedBackoff(attempt))
			continue
		}

		if resp.StatusCode >= 400 {
			apiErr := &APIError{StatusCode: resp.StatusCode}
			_ = json.Unmarshal(data, apiErr)
			if apiErr.Message == "" {
				apiErr.Message = string(data)
			}
			return nil, apiErr
		}

		return data, nil
	}
	return nil, fmt.Errorf("surf: request failed after %d attempts", c.maxRetries+1)
}

// cappedBackoff returns an exponential backoff duration for the given attempt,
// saturating at attempt=6 (64s→60s cap) to prevent integer overflow on large MaxRetries.
func cappedBackoff(attempt int) time.Duration {
	secs := 1 << uint(min(attempt, 6))
	if secs > 60 {
		secs = 60
	}
	return time.Duration(secs) * time.Second
}

func (c *Client) get(path string, params url.Values) (json.RawMessage, error) {
	data, err := c.do("GET", path, params, nil)
	return json.RawMessage(data), err
}

func (c *Client) post(path string, body interface{}) (json.RawMessage, error) {
	data, err := c.do("POST", path, nil, body)
	return json.RawMessage(data), err
}

func (c *Client) put(path string, body interface{}) (json.RawMessage, error) {
	data, err := c.do("PUT", path, nil, body)
	return json.RawMessage(data), err
}

func (c *Client) patch(path string, body interface{}) (json.RawMessage, error) {
	data, err := c.do("PATCH", path, nil, body)
	return json.RawMessage(data), err
}

func (c *Client) del(path string) error {
	_, err := c.do("DELETE", path, nil, nil)
	return err
}

func (c *Client) getRaw(path string, params url.Values) ([]byte, error) {
	return c.do("GET", path, params, nil)
}

func p(key, val string) url.Values {
	v := url.Values{}
	if val != "" {
		v.Set(key, val)
	}
	return v
}

func atoi(s string) int {
	n, _ := strconv.Atoi(s)
	return n
}

// Paginator iterates lazily over a cursor-paginated endpoint.
// Call Next() to check whether an item is available (it fetches the next page
// when the buffer is exhausted), then call Item() at most once to retrieve the
// item and advance the pointer. It is safe to break out of the loop without
// calling Item(). Check Err() after the loop.
//
//	pager := client.Paginate("/feed/posts", "posts", url.Values{"surf_id": {"surf/topic/technology"}}, 0)
//	for pager.Next() {
//	    var post map[string]interface{}
//	    _ = json.Unmarshal(pager.Item(), &post)
//	}
//	if err := pager.Err(); err != nil { ... }
type Paginator struct {
	c      *Client
	path   string
	key    string
	params url.Values
	limit  int // ≤ 0 means no limit

	buf       []json.RawMessage
	pos       int
	done      bool
	fetched   int
	err       error
	itemReady bool // true after Next() returns true; cleared by Item()
}

// Paginate returns a Paginator that lazily walks a cursor-paginated endpoint.
// limit ≤ 0 means no limit. params is shallow-copied and not mutated.
func (c *Client) Paginate(path, key string, params url.Values, limit int) *Paginator {
	cp := url.Values{}
	for k, v := range params {
		cp[k] = append([]string(nil), v...)
	}
	return &Paginator{c: c, path: path, key: key, params: cp, limit: limit}
}

// Next returns true if an item is available. It fetches the next page when the
// current page buffer is exhausted. Returns false when there are no more items
// or an error occurs. Calling Next() again before calling Item() is a misuse
// and sets Err(); it is safe to call Next() without Item() only when breaking
// out of the loop early.
func (pg *Paginator) Next() bool {
	if pg.err != nil {
		return false
	}
	if pg.limit > 0 && pg.fetched >= pg.limit {
		return false
	}
	// Drain the current page buffer before checking done — the final page
	// sets done=true but may still have unread items.
	if pg.pos < len(pg.buf) {
		if pg.itemReady {
			// Next() called again without consuming the previous item via Item().
			pg.err = fmt.Errorf("surf: paginate: Next() called again without a preceding Item() call")
			return false
		}
		pg.itemReady = true
		return true
	}
	if pg.done {
		return false
	}
	// Fetch the next page.
	raw, err := pg.c.get(pg.path, pg.params)
	if err != nil {
		pg.err = err
		return false
	}
	var page map[string]json.RawMessage
	if err := json.Unmarshal(raw, &page); err != nil {
		pg.err = fmt.Errorf("surf: paginate: parse response: %w", err)
		return false
	}
	keyData, ok := page[pg.key]
	if !ok {
		pg.done = true
		return false
	}
	var items []json.RawMessage
	if err := json.Unmarshal(keyData, &items); err != nil {
		pg.err = fmt.Errorf("surf: paginate: key %q is not an array: %w", pg.key, err)
		return false
	}
	if len(items) == 0 {
		pg.done = true
		return false
	}
	pg.buf = items
	pg.pos = 0
	pg.itemReady = true
	// Extract cursor for the next page. JSON null is treated as absent
	// (no more pages) to match Python/TypeScript/Java behaviour.
	var cursor string
	for _, field := range []string{"cursor", "next_cursor"} {
		if v, ok := page[field]; ok {
			if string(v) == "null" {
				continue // treat null as absent; check next_cursor
			}
			if err := json.Unmarshal(v, &cursor); err != nil {
				pg.err = fmt.Errorf("surf: paginate: parse %q field: %w", field, err)
				return false
			}
			if cursor != "" {
				break
			}
		}
	}
	if cursor == "" {
		pg.done = true // no more pages after this batch
	} else {
		pg.params.Set("cursor", cursor)
	}
	return true
}

// Item returns the current item and advances the internal pointer.
// May be called at most once after a successful Next(). Calling Item() without
// a preceding Next(), or calling it a second time before the next Next(), sets
// Err() and returns nil. It is safe to call Next() without calling Item()
// (e.g., when breaking out of the loop early).
func (pg *Paginator) Item() json.RawMessage {
	if !pg.itemReady {
		pg.err = fmt.Errorf("surf: paginate: Item() called without a preceding Next() or called more than once per Next()")
		return nil
	}
	pg.itemReady = false
	item := pg.buf[pg.pos]
	pg.pos++
	pg.fetched++
	return item
}

// Err returns the first error encountered, or nil.
func (pg *Paginator) Err() error {
	return pg.err
}

// PostsOptions for feed post queries.
type PostsOptions struct {
	Limit    int
	Cursor   string
	Sort     string
	Services string // filter by network: "mastodon", "bluesky", "rss"
}

func (o *PostsOptions) params(surfId string) url.Values {
	v := url.Values{"surf_id": {surfId}}
	if o != nil {
		if o.Limit > 0 {
			v.Set("limit", strconv.Itoa(o.Limit))
		}
		if o.Cursor != "" {
			v.Set("cursor", o.Cursor)
		}
		if o.Sort != "" {
			v.Set("sort", o.Sort)
		}
		if o.Services != "" {
			v.Set("services", o.Services)
		}
	}
	return v
}

// =========================================================================
// Feeds
// =========================================================================

// FeedsAPI provides access to feed and post operations.
type FeedsAPI struct{ c *Client }

func (a *FeedsAPI) Get(surfId string) (json.RawMessage, error) {
	return a.c.get("/feed", url.Values{"surf_id": {surfId}})
}

func (a *FeedsAPI) GetPosts(surfId string, opts *PostsOptions) (json.RawMessage, error) {
	return a.c.get("/feed/posts", opts.params(surfId))
}

func (a *FeedsAPI) GetPost(id string, thread bool) (json.RawMessage, error) {
	v := url.Values{"id": {id}}
	if thread {
		v.Set("thread", "true")
	}
	return a.c.get("/post", v)
}

func (a *FeedsAPI) GetFollowing(limit int) (json.RawMessage, error) {
	return a.c.get("/feed/following", url.Values{"limit": {strconv.Itoa(limit)}})
}

// Write operations (require write:statuses scope).
// The service parameter is optional — omit it to use the default linked account (prefers Bluesky),
// or pass exactly one value ("bluesky" or "mastodon") to target a specific service.
// Passing more than one value returns an error.

func svcParams(service []string) (url.Values, error) {
	if len(service) > 1 {
		return nil, fmt.Errorf("surf: at most one service value may be provided, got %d", len(service))
	}
	if len(service) == 0 || service[0] == "" {
		return nil, nil
	}
	return url.Values{"service": {service[0]}}, nil
}

func (a *FeedsAPI) CreatePost(status, visibility string, service ...string) (json.RawMessage, error) {
	if visibility == "" {
		visibility = "public"
	}
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/statuses", params, map[string]string{"status": status, "visibility": visibility})
	return json.RawMessage(data), err
}

func (a *FeedsAPI) Favourite(id string, service ...string) (json.RawMessage, error) {
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/statuses/"+url.PathEscape(id)+"/favourite", params, nil)
	return json.RawMessage(data), err
}

func (a *FeedsAPI) Unfavourite(id string, service ...string) (json.RawMessage, error) {
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/statuses/"+url.PathEscape(id)+"/unfavourite", params, nil)
	return json.RawMessage(data), err
}

func (a *FeedsAPI) Boost(id string, service ...string) (json.RawMessage, error) {
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/statuses/"+url.PathEscape(id)+"/reblog", params, nil)
	return json.RawMessage(data), err
}

func (a *FeedsAPI) Unboost(id string, service ...string) (json.RawMessage, error) {
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/statuses/"+url.PathEscape(id)+"/unreblog", params, nil)
	return json.RawMessage(data), err
}

func (a *FeedsAPI) Bookmark(id string, service ...string) (json.RawMessage, error) {
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/statuses/"+url.PathEscape(id)+"/bookmark", params, nil)
	return json.RawMessage(data), err
}

func (a *FeedsAPI) Unbookmark(id string, service ...string) (json.RawMessage, error) {
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/statuses/"+url.PathEscape(id)+"/unbookmark", params, nil)
	return json.RawMessage(data), err
}

func (a *FeedsAPI) DeletePost(id string, service ...string) error {
	params, err := svcParams(service)
	if err != nil {
		return err
	}
	_, err = a.c.do("DELETE", "/statuses/"+url.PathEscape(id), params, nil)
	return err
}

func (a *FeedsAPI) GetSpeedDial() (json.RawMessage, error) {
	return a.c.get("/feed/speeddial", nil)
}

// =========================================================================
// Search
// =========================================================================

// SearchAPI provides search operations across feeds, posts, accounts, and podcasts.
type SearchAPI struct{ c *Client }

func (a *SearchAPI) Search(q, typ string, limit int) (json.RawMessage, error) {
	if typ == "" {
		typ = "feeds"
	}
	return a.c.get("/search", url.Values{"q": {q}, "type": {typ}, "limit": {strconv.Itoa(limit)}})
}

func (a *SearchAPI) Feeds(q string, limit int) (json.RawMessage, error) {
	return a.Search(q, "feeds", limit)
}
func (a *SearchAPI) Posts(q string, limit int) (json.RawMessage, error) {
	return a.Search(q, "posts", limit)
}
func (a *SearchAPI) Accounts(q string, limit int) (json.RawMessage, error) {
	return a.Search(q, "accounts", limit)
}
func (a *SearchAPI) Podcasts(q string, limit int) (json.RawMessage, error) {
	return a.Search(q, "podcasts", limit)
}

func (a *SearchAPI) Discover(typ, surfId string, limit int) (json.RawMessage, error) {
	v := url.Values{"type": {typ}, "limit": {strconv.Itoa(limit)}}
	if surfId != "" {
		v.Set("surf_id", surfId)
	}
	return a.c.get("/search/discover", v)
}

// =========================================================================
// AI (use:ai scope, 10/day)
// =========================================================================

// AIAPI provides AI-powered features including natural language search and feed summaries.
type AIAPI struct{ c *Client }

func (a *AIAPI) Ask(query string, k int) (json.RawMessage, error) {
	return a.c.get("/ai/ask", url.Values{"query": {query}, "k": {strconv.Itoa(k)}})
}

func (a *AIAPI) FeedSummary(surfId string, limit int) (json.RawMessage, error) {
	return a.c.get("/ai/feed-summary", url.Values{"surf_id": {surfId}, "limit": {strconv.Itoa(limit)}})
}

func (a *AIAPI) ThreadSummary(postAT string) (json.RawMessage, error) {
	return a.c.get("/ai/thread-summary", url.Values{"post_at": {postAT}})
}

func (a *AIAPI) BuildFeed(prompt string, feedId string) (json.RawMessage, error) {
	body := map[string]string{"prompt": prompt}
	if feedId != "" {
		body["feed_id"] = feedId
	}
	return a.c.post("/ai/feed-builder", body)
}

// =========================================================================
// Account
// =========================================================================

// AccountAPI provides account lookup and profile management.
type AccountAPI struct{ c *Client }

func (a *AccountAPI) Get() (json.RawMessage, error) { return a.c.get("/account", nil) }
func (a *AccountAPI) Update(fields interface{}) (json.RawMessage, error) {
	return a.c.put("/account", fields)
}
func (a *AccountAPI) Lookup(account string) (json.RawMessage, error) {
	return a.c.get("/account/lookup", url.Values{"account": {account}})
}
func (a *AccountAPI) GetLinks() (json.RawMessage, error) { return a.c.get("/account/links", nil) }
func (a *AccountAPI) AddLink(link interface{}) (json.RawMessage, error) {
	return a.c.post("/account/links", link)
}
func (a *AccountAPI) UpdateLink(id string, link interface{}) (json.RawMessage, error) {
	return a.c.put("/account/links/"+id, link)
}
func (a *AccountAPI) DeleteLink(id string) error { return a.c.del("/account/links/" + id) }
func (a *AccountAPI) Follow(accountId string, service ...string) (json.RawMessage, error) {
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/accounts/"+accountId+"/follow", params, nil)
	return json.RawMessage(data), err
}
func (a *AccountAPI) Unfollow(accountId string, service ...string) (json.RawMessage, error) {
	params, err := svcParams(service)
	if err != nil {
		return nil, err
	}
	data, err := a.c.do("POST", "/accounts/"+accountId+"/unfollow", params, nil)
	return json.RawMessage(data), err
}
func (a *AccountAPI) GetConnectedApps() (json.RawMessage, error) {
	return a.c.get("/account/connected-apps", nil)
}
func (a *AccountAPI) RevokeConnectedApp(authorizationId int) (json.RawMessage, error) {
	return a.c.post(fmt.Sprintf("/account/connected-apps/%d/revoke", authorizationId), nil)
}

// =========================================================================
// Content
// =========================================================================

// ContentAPI provides URL resolution, article extraction, and language detection.
type ContentAPI struct{ c *Client }

func (a *ContentAPI) Resolve(u string) (json.RawMessage, error) {
	return a.c.get("/content/resolve", url.Values{"url": {u}})
}
func (a *ContentAPI) Extract(u, typ string) (json.RawMessage, error) {
	if typ == "" {
		typ = "article"
	}
	return a.c.get("/content/extract", url.Values{"url": {u}, "type": {typ}})
}
func (a *ContentAPI) Language(u string) (json.RawMessage, error) {
	return a.c.get("/content/language", url.Values{"url": {u}})
}
func (a *ContentAPI) Topics(u string) (json.RawMessage, error) {
	return a.c.get("/content/topics", url.Values{"url": {u}})
}
func (a *ContentAPI) Enrich(postId string) (json.RawMessage, error) {
	return a.c.get("/content/enrich", url.Values{"postId": {postId}})
}

// =========================================================================
// Images
// =========================================================================

// ImagesAPI provides AI-powered image analysis.
type ImagesAPI struct{ c *Client }

func (a *ImagesAPI) Info(u string) (json.RawMessage, error) {
	return a.c.get("/image/info", url.Values{"url": {u}})
}
func (a *ImagesAPI) Resize(u, size string) ([]byte, error) {
	return a.c.getRaw("/image/resize", url.Values{"url": {u}, "size": {size}})
}
func (a *ImagesAPI) Colors(u string, k int) ([]byte, error) {
	return a.c.getRaw("/image/colors", url.Values{"url": {u}, "k": {strconv.Itoa(k)}})
}
func (a *ImagesAPI) Moderate(u string) (json.RawMessage, error) {
	return a.c.get("/image/moderate", url.Values{"url": {u}})
}

// =========================================================================
// Audio
// =========================================================================

// AudioAPI provides radio stations, briefings, podcasts, and text-to-speech.
type AudioAPI struct{ c *Client }

func (a *AudioAPI) ListStations() (json.RawMessage, error) {
	return a.c.get("/audio/radio/stations", nil)
}
func (a *AudioAPI) GetStation(id string) (json.RawMessage, error) {
	return a.c.get("/audio/radio/stations/"+id, nil)
}
func (a *AudioAPI) CreateStation(feedSurfId string) (json.RawMessage, error) {
	return a.c.post("/audio/radio/stations", map[string]string{"feed_surf_id": feedSurfId})
}
func (a *AudioAPI) GenerateProgram(stationId string) (json.RawMessage, error) {
	return a.c.post("/audio/radio/stations/"+stationId+"/generate", nil)
}
func (a *AudioAPI) GetProgram(programId string) (json.RawMessage, error) {
	return a.c.get("/audio/radio/programs/"+programId, nil)
}
func (a *AudioAPI) GenerateBriefing() (json.RawMessage, error) {
	return a.c.post("/audio/briefing/generate", nil)
}
func (a *AudioAPI) GetBriefing(id string) (json.RawMessage, error) {
	if id == "" {
		return a.c.get("/audio/briefing/latest", nil)
	}
	return a.c.get("/audio/briefing/"+id, nil)
}
func (a *AudioAPI) GetTranscript(episodeUrl string) (json.RawMessage, error) {
	return a.c.get("/audio/transcript", url.Values{"episode_url": {episodeUrl}})
}
func (a *AudioAPI) GetDailyQuiz() (json.RawMessage, error) { return a.c.get("/audio/quiz/daily", nil) }
func (a *AudioAPI) TextToSpeech(text, voice string) ([]byte, error) {
	if voice == "" {
		voice = "en-US-AriaNeural"
	}
	return a.c.do("POST", "/audio/tts", nil, map[string]string{"text": text, "voice": voice})
}

// =========================================================================
// Notifications
// =========================================================================

// NotificationsAPI provides notification feed access and badge management.
type NotificationsAPI struct{ c *Client }

func (a *NotificationsAPI) List(limit int, cursor string) (json.RawMessage, error) {
	v := url.Values{"limit": {strconv.Itoa(limit)}}
	if cursor != "" {
		v.Set("cursor", cursor)
	}
	return a.c.get("/notifications", v)
}
func (a *NotificationsAPI) MarkRead() (json.RawMessage, error) {
	return a.c.post("/notifications/read", nil)
}

// =========================================================================
// Preferences
// =========================================================================

// PreferencesAPI provides user preference management.
type PreferencesAPI struct{ c *Client }

func (a *PreferencesAPI) Get() (json.RawMessage, error) { return a.c.get("/preferences/account", nil) }
func (a *PreferencesAPI) Update(prefs interface{}) (json.RawMessage, error) {
	return a.c.patch("/preferences/account", prefs)
}

// =========================================================================
// Custom Feeds
// =========================================================================

// FeedTheme builds the clean theme object for create/update.
// Uses semantic color names and separates header from color concerns.
//
// Example:
//
//	theme := surf.FeedTheme{
//	    Header: &surf.FeedThemeHeader{
//	        Image:     "https://cdn.example.com/logo.png",
//	        ImageSize: map[string]interface{}{"width": 600, "height": 272},
//	    },
//	    Colors: &surf.FeedThemeColors{
//	        Light: map[string]string{"surface": "#EFEADD", "surfaceHeader": "#005F5F"},
//	    },
//	}
//	client.CustomFeeds.Create(map[string]interface{}{
//	    "title": "My Feed",
//	    "theme": theme.ToMap(),
//	})
type FeedTheme struct {
	Header *FeedThemeHeader
	Colors *FeedThemeColors
}

type FeedThemeHeader struct {
	Image        string
	ImageDark    string
	ImageSize    map[string]interface{}
	ImagePadding map[string]interface{}
	Layout       string // "banner", "compact", or "minimal"
	Responsive   *FeedThemeResponsive
}

type FeedThemeResponsive struct {
	Compact *FeedThemeHeaderOverride
}

type FeedThemeHeaderOverride struct {
	ImageSize    map[string]interface{}
	ImagePadding map[string]interface{}
}

type FeedThemeColors struct {
	Light map[string]string
	Dark  map[string]string
}

// ToMap converts the theme to the map accepted by the API.
func (t *FeedTheme) ToMap() map[string]interface{} {
	m := map[string]interface{}{}
	if t.Header != nil {
		h := map[string]interface{}{}
		if t.Header.Image != "" {
			h["image"] = t.Header.Image
		}
		if t.Header.ImageDark != "" {
			h["imageDark"] = t.Header.ImageDark
		}
		if t.Header.ImageSize != nil {
			h["imageSize"] = t.Header.ImageSize
		}
		if t.Header.ImagePadding != nil {
			h["imagePadding"] = t.Header.ImagePadding
		}
		if t.Header.Layout != "" {
			h["layout"] = t.Header.Layout
		}
		if t.Header.Responsive != nil && t.Header.Responsive.Compact != nil {
			c := map[string]interface{}{}
			if t.Header.Responsive.Compact.ImageSize != nil {
				c["imageSize"] = t.Header.Responsive.Compact.ImageSize
			}
			if t.Header.Responsive.Compact.ImagePadding != nil {
				c["imagePadding"] = t.Header.Responsive.Compact.ImagePadding
			}
			if len(c) > 0 {
				h["responsive"] = map[string]interface{}{"compact": c}
			}
		}
		if len(h) > 0 {
			m["header"] = h
		}
	}
	if t.Colors != nil {
		c := map[string]interface{}{}
		if t.Colors.Light != nil {
			c["light"] = t.Colors.Light
		}
		if t.Colors.Dark != nil {
			c["dark"] = t.Colors.Dark
		}
		if len(c) > 0 {
			m["colors"] = c
		}
	}
	return m
}

// Operator is the role an operator (source) plays within a custom feed.
type Operator string

const (
	OperatorSource           Operator = "source"
	OperatorInclude          Operator = "include"
	OperatorFilteringInclude Operator = "filtering_include"
	OperatorExclude          Operator = "exclude"
	OperatorScore            Operator = "score"
)

// FeedOperatorFilter is a filter applied to a custom-feed operator.
type FeedOperatorFilter struct {
	SurfID   string   `json:"surfId"`
	Operator Operator `json:"operator,omitempty"`
}

// FeedOperator is the writable shape for a custom-feed operator — the fields the
// API accepts on create. Server-assigned fields (id, created, last_modified) are
// not included.
//
// Common case:
//
//	surf.NewFeedOperatorSource("surf/topic/artificial-intelligence")
type FeedOperator struct {
	SurfID   string               `json:"surfId"`
	Operator Operator             `json:"operator,omitempty"`
	Filters  []FeedOperatorFilter `json:"filters,omitempty"`
}

// NewFeedOperatorSource returns a source FeedOperator for the given surfId.
func NewFeedOperatorSource(surfID string) FeedOperator {
	return FeedOperator{SurfID: surfID, Operator: OperatorSource}
}

// NewFeedOperator returns a FeedOperator with the given surfId and operator role.
func NewFeedOperator(surfID string, op Operator) FeedOperator {
	return FeedOperator{SurfID: surfID, Operator: op}
}

// CustomFeedsAPI provides custom feed CRUD and operator management.
type CustomFeedsAPI struct{ c *Client }

func (a *CustomFeedsAPI) List() (json.RawMessage, error)         { return a.c.get("/custom", nil) }
func (a *CustomFeedsAPI) Get(id string) (json.RawMessage, error) { return a.c.get("/custom/"+id, nil) }
func (a *CustomFeedsAPI) Create(body interface{}) (json.RawMessage, error) {
	return a.c.post("/custom", body)
}

// CreateWithOperators creates a new custom feed with typed FeedOperator values.
//
//	client.CustomFeeds.CreateWithOperators("AI News", "Latest AI",
//	    surf.NewFeedOperatorSource("surf/topic/artificial-intelligence"),
//	    surf.NewFeedOperatorSource("surf/hashtag/machinelearning"),
//	)
func (a *CustomFeedsAPI) CreateWithOperators(title, description string, operators ...FeedOperator) (json.RawMessage, error) {
	body := map[string]interface{}{"title": title}
	if description != "" {
		body["description"] = description
	}
	if len(operators) > 0 {
		body["operators"] = operators
	}
	return a.c.post("/custom", body)
}
func (a *CustomFeedsAPI) Update(id string, body interface{}) (json.RawMessage, error) {
	return a.c.put("/custom/"+id, body)
}
func (a *CustomFeedsAPI) Delete(id string) error { return a.c.del("/custom/" + id) }
func (a *CustomFeedsAPI) Clone(id string) (json.RawMessage, error) {
	return a.c.post("/custom/"+id+"/clone", nil)
}
func (a *CustomFeedsAPI) Publish(id string) (json.RawMessage, error) {
	return a.c.post("/custom/"+id+"/publish", nil)
}
func (a *CustomFeedsAPI) Unpublish(id string) (json.RawMessage, error) {
	return a.c.post("/custom/"+id+"/unpublish", nil)
}
func (a *CustomFeedsAPI) AddOperator(feedId string, op interface{}) (json.RawMessage, error) {
	return a.c.post("/custom/"+feedId+"/operators", []interface{}{op})
}
func (a *CustomFeedsAPI) AddOperators(feedId string, ops []interface{}) (json.RawMessage, error) {
	return a.c.post("/custom/"+feedId+"/operators", ops)
}
func (a *CustomFeedsAPI) UpdateOperator(feedId, opId string, op interface{}) (json.RawMessage, error) {
	return a.c.put("/custom/"+feedId+"/operators/"+opId, op)
}
func (a *CustomFeedsAPI) RemoveOperator(feedId, opId string) error {
	return a.c.del("/custom/" + feedId + "/operators/" + opId)
}

// =========================================================================
// Media
// =========================================================================

// MediaAPI provides media upload for posts.
type MediaAPI struct{ c *Client }

// Upload is not yet implemented — requires multipart form encoding.
func (a *MediaAPI) Upload(filename string, data io.Reader) (json.RawMessage, error) {
	return nil, fmt.Errorf("surf: media upload not yet implemented in Go SDK")
}

// GenerateImage starts AI generation of a feed cover image (Stable Diffusion XL)
// and returns immediately. Async submit/poll: the response is {"key", "url",
// "status": "pending"} — generation runs server-side and can take a couple of
// minutes. Poll GenerateImageStatus with the key until "done", then use the url;
// or call GenerateImageAndWait to do both. Requires the use:ai scope. skipRefiner
// trades quality for speed.
func (a *MediaAPI) GenerateImage(prompt string, skipRefiner bool) (json.RawMessage, error) {
	return a.c.post("/media/generate-image", map[string]interface{}{
		"prompt":      prompt,
		"skipRefiner": skipRefiner,
	})
}

// GenerateImageStatus polls a generation job started by GenerateImage. The
// response is {"status": "pending"|"done"|"failed"|"not_found"}.
func (a *MediaAPI) GenerateImageStatus(key string) (json.RawMessage, error) {
	return a.c.get("/media/generate-image/status", url.Values{"key": {key}})
}

// GenerateImageAndWait submits a generation job and polls until it completes,
// returning the image URL. It polls every pollInterval up to timeout (pass 0 for
// the defaults: 4s interval, 10m timeout). Requires the use:ai scope.
func (a *MediaAPI) GenerateImageAndWait(prompt string, skipRefiner bool, pollInterval, timeout time.Duration) (string, error) {
	if pollInterval <= 0 {
		pollInterval = 4 * time.Second
	}
	if timeout <= 0 {
		timeout = 10 * time.Minute
	}
	raw, err := a.GenerateImage(prompt, skipRefiner)
	if err != nil {
		return "", err
	}
	var submit struct {
		Key string `json:"key"`
		URL string `json:"url"`
	}
	if err := json.Unmarshal(raw, &submit); err != nil {
		return "", err
	}
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		time.Sleep(pollInterval)
		sraw, err := a.GenerateImageStatus(submit.Key)
		if err != nil {
			// Fail fast on permanent errors (auth/scope/not-found); only keep
			// polling through transient ones (429 rate limit, 5xx, network).
			var apiErr *APIError
			if errors.As(err, &apiErr) &&
				apiErr.StatusCode >= 400 && apiErr.StatusCode < 500 && apiErr.StatusCode != 429 {
				return "", err
			}
			continue
		}
		var st struct {
			Status string `json:"status"`
		}
		if err := json.Unmarshal(sraw, &st); err != nil {
			continue
		}
		switch st.Status {
		case "done":
			return submit.URL, nil
		case "failed", "not_found":
			return "", fmt.Errorf("surf: image generation %s", st.Status)
		}
	}
	return "", fmt.Errorf("surf: image generation timed out")
}

// =========================================================================
// RTB (Real-Time Bidding)
// =========================================================================

// RTBClient is a separate client for the Surf RTB API.
// Uses the same API key as Client but targets RTB endpoints.
// The API key must include rtb:* scopes.
type RTBClient struct {
	APIKey     string
	BaseURL    string
	HTTP       *http.Client
	maxRetries int // mirrors Client: retry 429/5xx/transient errors
}

// RTBClientOption configures an RTBClient.
type RTBClientOption func(*RTBClient)

// WithRTBMaxRetries sets the number of retries after the initial attempt on 429,
// 5xx, or transient network errors (default 3; 0 disables retry). Mirrors
// WithMaxRetries on the main Client.
func WithRTBMaxRetries(n int) RTBClientOption {
	return func(r *RTBClient) {
		if n >= 0 {
			r.maxRetries = n
		}
	}
}

// NewRTBClient creates an RTB client. Uses the same API key format as NewClient.
// Pass RTBClientOption values to override defaults.
func NewRTBClient(apiKey string, opts ...RTBClientOption) *RTBClient {
	r := &RTBClient{
		APIKey:     apiKey,
		BaseURL:    "https://surf.social",
		HTTP:       &http.Client{Timeout: 10 * time.Second},
		maxRetries: 3,
	}
	for _, opt := range opts {
		opt(r)
	}
	return r
}

func (r *RTBClient) url(path string) string {
	return r.BaseURL + "/devportal/v1/rtb" + path
}

func (r *RTBClient) do(method, path string, body interface{}, params url.Values) (json.RawMessage, error) {
	u := r.url(path)
	if len(params) > 0 {
		u += "?" + params.Encode()
	}

	var bodyBytes []byte
	if body != nil {
		var err error
		bodyBytes, err = json.Marshal(body)
		if err != nil {
			return nil, err
		}
	}

	// Retry on 429 (respecting Retry-After), 5xx, and transient network errors,
	// matching Client.do so RTB and the main client behave the same way.
	for attempt := 0; attempt <= r.maxRetries; attempt++ {
		var reqBody io.Reader
		if bodyBytes != nil {
			reqBody = bytes.NewReader(bodyBytes)
		}
		req, err := http.NewRequest(method, u, reqBody)
		if err != nil {
			return nil, err
		}
		req.Header.Set("X-API-Key", r.APIKey)
		req.Header.Set("User-Agent", userAgent)
		req.Header.Set("Accept", "application/json")
		if bodyBytes != nil {
			req.Header.Set("Content-Type", "application/json")
		}

		resp, err := r.HTTP.Do(req)
		if err != nil {
			if attempt < r.maxRetries {
				time.Sleep(cappedBackoff(attempt))
				continue
			}
			return nil, err
		}

		data, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if readErr != nil {
			return nil, readErr
		}

		if resp.StatusCode == 429 && attempt < r.maxRetries {
			retryAfter := atoi(resp.Header.Get("Retry-After"))
			if retryAfter <= 0 {
				retryAfter = int(cappedBackoff(attempt).Seconds())
			}
			if retryAfter > 60 {
				retryAfter = 60
			}
			time.Sleep(time.Duration(retryAfter) * time.Second)
			continue
		}

		if resp.StatusCode >= 500 && attempt < r.maxRetries {
			time.Sleep(cappedBackoff(attempt))
			continue
		}

		if resp.StatusCode >= 400 {
			apiErr := &APIError{StatusCode: resp.StatusCode}
			_ = json.Unmarshal(data, apiErr)
			if apiErr.Message == "" {
				apiErr.Message = string(data)
			}
			return nil, apiErr
		}

		return json.RawMessage(data), nil
	}
	return nil, fmt.Errorf("surf: RTB request failed after %d attempts", r.maxRetries+1)
}

// Bid sends an OpenRTB 2.5 bid request. Set sandbox=true for test mode.
func (r *RTBClient) Bid(request map[string]interface{}, sandbox bool) (json.RawMessage, error) {
	body := request
	if sandbox {
		body = make(map[string]interface{}, len(request)+1)
		for k, v := range request {
			body[k] = v
		}
		body["test"] = 1
	}
	return r.do("POST", "/bid", body, nil)
}

// Reports gets RTB performance reports.
func (r *RTBClient) Reports(days int, granularity string) (json.RawMessage, error) {
	params := url.Values{"days": {strconv.Itoa(days)}, "granularity": {granularity}}
	return r.do("GET", "/reports", nil, params)
}

// Config gets RTB configuration and tier info.
func (r *RTBClient) Config() (json.RawMessage, error) {
	return r.do("GET", "/config", nil, nil)
}

// Scopes lists available RTB scopes.
func (r *RTBClient) Scopes() (json.RawMessage, error) {
	return r.do("GET", "/scopes", nil, nil)
}

// AdsTxt returns your personalized ads.txt entry for authorizing Surf as a
// seller. Add the returned entries to the ads.txt at the root of each domain
// where you display Surf ads.
func (r *RTBClient) AdsTxt() (json.RawMessage, error) {
	return r.do("GET", "/ads-txt", nil, nil)
}
