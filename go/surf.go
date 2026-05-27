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
	userAgent      = "surf-api-go/0.2.0"
)

// Client is the Surf API client.
type Client struct {
	APIKey  string
	BaseURL string
	HTTP    *http.Client

	// Sub-clients
	Feeds        *FeedsAPI
	Search       *SearchAPI
	AI           *AIAPI
	Account      *AccountAPI
	Content      *ContentAPI
	Images       *ImagesAPI
	Audio        *AudioAPI
	Notifications *NotificationsAPI
	Preferences  *PreferencesAPI
	CustomFeeds  *CustomFeedsAPI
	Media        *MediaAPI

	// RateLimit is updated after each request.
	RateLimit *RateLimitInfo
}

// RateLimitInfo holds rate limit data from response headers.
type RateLimitInfo struct {
	Limit     int
	Remaining int
	Reset     string
}

// NewClient creates a new Surf API client.
func NewClient(apiKey string) *Client {
	c := &Client{
		APIKey:  apiKey,
		BaseURL: DefaultBaseURL,
		HTTP:    &http.Client{Timeout: 30 * time.Second},
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

// APIError is returned for non-2xx responses.
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

	var reqBody io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("surf: marshal body: %w", err)
		}
		reqBody = bytes.NewReader(b)
	}

	req, err := http.NewRequest(method, u, reqBody)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-API-Key", c.APIKey)
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	// Update rate limit info
	c.RateLimit = &RateLimitInfo{
		Limit:     atoi(resp.Header.Get("X-RateLimit-Limit")),
		Remaining: atoi(resp.Header.Get("X-RateLimit-Remaining")),
		Reset:     resp.Header.Get("X-RateLimit-Reset"),
	}

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
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

// PostsOptions for feed post queries.
type PostsOptions struct {
	Limit   int
	Cursor  string
	Sort    string
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
	}
	return v
}

// =========================================================================
// Feeds
// =========================================================================

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

// Write operations (require write:statuses scope)
func (a *FeedsAPI) CreatePost(status, visibility string) (json.RawMessage, error) {
	if visibility == "" { visibility = "public" }
	return a.c.post("/statuses", map[string]string{"status": status, "visibility": visibility})
}
func (a *FeedsAPI) Favourite(id string) (json.RawMessage, error) { return a.c.post("/statuses/"+id+"/favourite", nil) }
func (a *FeedsAPI) Unfavourite(id string) (json.RawMessage, error) { return a.c.post("/statuses/"+id+"/unfavourite", nil) }
func (a *FeedsAPI) Boost(id string) (json.RawMessage, error) { return a.c.post("/statuses/"+id+"/reblog", nil) }
func (a *FeedsAPI) Unboost(id string) (json.RawMessage, error) { return a.c.post("/statuses/"+id+"/unreblog", nil) }
func (a *FeedsAPI) Bookmark(id string) (json.RawMessage, error) { return a.c.post("/statuses/"+id+"/bookmark", nil) }
func (a *FeedsAPI) DeletePost(id string) error { return a.c.del("/statuses/"+id) }

func (a *FeedsAPI) GetSpeedDial() (json.RawMessage, error) {
	return a.c.get("/feed/speeddial", nil)
}

// =========================================================================
// Search
// =========================================================================

type SearchAPI struct{ c *Client }

func (a *SearchAPI) Search(q, typ string, limit int) (json.RawMessage, error) {
	if typ == "" {
		typ = "feeds"
	}
	return a.c.get("/search", url.Values{"q": {q}, "type": {typ}, "limit": {strconv.Itoa(limit)}})
}

func (a *SearchAPI) Feeds(q string, limit int) (json.RawMessage, error) { return a.Search(q, "feeds", limit) }
func (a *SearchAPI) Posts(q string, limit int) (json.RawMessage, error) { return a.Search(q, "posts", limit) }
func (a *SearchAPI) Accounts(q string, limit int) (json.RawMessage, error) { return a.Search(q, "accounts", limit) }
func (a *SearchAPI) Podcasts(q string, limit int) (json.RawMessage, error) { return a.Search(q, "podcasts", limit) }

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

type AccountAPI struct{ c *Client }

func (a *AccountAPI) Get() (json.RawMessage, error)          { return a.c.get("/account", nil) }
func (a *AccountAPI) Update(fields interface{}) (json.RawMessage, error) { return a.c.put("/account", fields) }
func (a *AccountAPI) Lookup(account string) (json.RawMessage, error) {
	return a.c.get("/account/lookup", url.Values{"account": {account}})
}
func (a *AccountAPI) GetLinks() (json.RawMessage, error) { return a.c.get("/account/links", nil) }
func (a *AccountAPI) AddLink(link interface{}) (json.RawMessage, error) { return a.c.post("/account/links", link) }
func (a *AccountAPI) UpdateLink(id string, link interface{}) (json.RawMessage, error) {
	return a.c.put("/account/links/"+id, link)
}
func (a *AccountAPI) DeleteLink(id string) error { return a.c.del("/account/links/" + id) }
func (a *AccountAPI) Follow(accountId string) (json.RawMessage, error) { return a.c.post("/accounts/"+accountId+"/follow", nil) }
func (a *AccountAPI) Unfollow(accountId string) (json.RawMessage, error) { return a.c.post("/accounts/"+accountId+"/unfollow", nil) }
func (a *AccountAPI) GetConnectedApps() (json.RawMessage, error) { return a.c.get("/account/connected-apps", nil) }
func (a *AccountAPI) RevokeConnectedApp(authorizationId int) (json.RawMessage, error) {
	return a.c.post(fmt.Sprintf("/account/connected-apps/%d/revoke", authorizationId), nil)
}

// =========================================================================
// Content
// =========================================================================

type ContentAPI struct{ c *Client }

func (a *ContentAPI) Resolve(u string) (json.RawMessage, error) { return a.c.get("/content/resolve", url.Values{"url": {u}}) }
func (a *ContentAPI) Extract(u, typ string) (json.RawMessage, error) {
	if typ == "" {
		typ = "article"
	}
	return a.c.get("/content/extract", url.Values{"url": {u}, "type": {typ}})
}
func (a *ContentAPI) Language(u string) (json.RawMessage, error) { return a.c.get("/content/language", url.Values{"url": {u}}) }
func (a *ContentAPI) Topics(u string) (json.RawMessage, error)   { return a.c.get("/content/topics", url.Values{"url": {u}}) }
func (a *ContentAPI) Enrich(postId string) (json.RawMessage, error) {
	return a.c.get("/content/enrich", url.Values{"postId": {postId}})
}

// =========================================================================
// Images
// =========================================================================

type ImagesAPI struct{ c *Client }

func (a *ImagesAPI) Info(u string) (json.RawMessage, error) { return a.c.get("/image/info", url.Values{"url": {u}}) }
func (a *ImagesAPI) Resize(u, size string) ([]byte, error)  { return a.c.getRaw("/image/resize", url.Values{"url": {u}, "size": {size}}) }
func (a *ImagesAPI) Colors(u string, k int) ([]byte, error) {
	return a.c.getRaw("/image/colors", url.Values{"url": {u}, "k": {strconv.Itoa(k)}})
}
func (a *ImagesAPI) Moderate(u string) (json.RawMessage, error) { return a.c.get("/image/moderate", url.Values{"url": {u}}) }

// =========================================================================
// Audio
// =========================================================================

type AudioAPI struct{ c *Client }

func (a *AudioAPI) ListStations() (json.RawMessage, error) { return a.c.get("/audio/radio/stations", nil) }
func (a *AudioAPI) GetStation(id string) (json.RawMessage, error) { return a.c.get("/audio/radio/stations/"+id, nil) }
func (a *AudioAPI) CreateStation(feedSurfId string) (json.RawMessage, error) {
	return a.c.post("/audio/radio/stations", map[string]string{"feed_surf_id": feedSurfId})
}
func (a *AudioAPI) GenerateProgram(stationId string) (json.RawMessage, error) {
	return a.c.post("/audio/radio/stations/"+stationId+"/generate", nil)
}
func (a *AudioAPI) GetProgram(programId string) (json.RawMessage, error) {
	return a.c.get("/audio/radio/programs/"+programId, nil)
}
func (a *AudioAPI) GenerateBriefing() (json.RawMessage, error)   { return a.c.post("/audio/briefing/generate", nil) }
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

type NotificationsAPI struct{ c *Client }

func (a *NotificationsAPI) List(limit int, cursor string) (json.RawMessage, error) {
	v := url.Values{"limit": {strconv.Itoa(limit)}}
	if cursor != "" {
		v.Set("cursor", cursor)
	}
	return a.c.get("/notifications", v)
}
func (a *NotificationsAPI) MarkRead() (json.RawMessage, error) { return a.c.post("/notifications/read", nil) }

// =========================================================================
// Preferences
// =========================================================================

type PreferencesAPI struct{ c *Client }

func (a *PreferencesAPI) Get() (json.RawMessage, error) { return a.c.get("/preferences/account", nil) }
func (a *PreferencesAPI) Update(prefs interface{}) (json.RawMessage, error) {
	return a.c.patch("/preferences/account", prefs)
}

// =========================================================================
// Custom Feeds
// =========================================================================

type CustomFeedsAPI struct{ c *Client }

func (a *CustomFeedsAPI) List() (json.RawMessage, error)                 { return a.c.get("/custom", nil) }
func (a *CustomFeedsAPI) Get(id string) (json.RawMessage, error)         { return a.c.get("/custom/"+id, nil) }
func (a *CustomFeedsAPI) Create(body interface{}) (json.RawMessage, error) { return a.c.post("/custom", body) }
func (a *CustomFeedsAPI) Update(id string, body interface{}) (json.RawMessage, error) { return a.c.put("/custom/"+id, body) }
func (a *CustomFeedsAPI) Delete(id string) error                         { return a.c.del("/custom/" + id) }
func (a *CustomFeedsAPI) Clone(id string) (json.RawMessage, error)       { return a.c.post("/custom/"+id+"/clone", nil) }
func (a *CustomFeedsAPI) Publish(id string) (json.RawMessage, error)     { return a.c.post("/custom/"+id+"/publish", nil) }
func (a *CustomFeedsAPI) Unpublish(id string) (json.RawMessage, error)   { return a.c.post("/custom/"+id+"/unpublish", nil) }
func (a *CustomFeedsAPI) AddOperator(feedId string, op interface{}) (json.RawMessage, error) {
	return a.c.post("/custom/"+feedId+"/operators", op)
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

type MediaAPI struct{ c *Client }

// Upload is not yet implemented — requires multipart form encoding.
func (a *MediaAPI) Upload(filename string, data io.Reader) (json.RawMessage, error) {
	return nil, fmt.Errorf("surf: media upload not yet implemented in Go SDK")
}
