//go:build integration

package surf

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

// isBareArrayError reports whether err indicates the paginator received a
// top-level JSON array instead of an object. Uses errors.As on the wrapped
// *json.UnmarshalTypeError so the check is stable across Go versions.
func isBareArrayError(err error) bool {
	var ute *json.UnmarshalTypeError
	return errors.As(err, &ute) && ute.Value == "array"
}

// testClient returns a configured Client, skipping the test if SURF_API_TEST_TOKEN is not set.
func testClient(t *testing.T) *Client {
	t.Helper()
	token := os.Getenv("SURF_API_TEST_TOKEN")
	if token == "" {
		t.Skip("SURF_API_TEST_TOKEN not set")
	}
	c := NewClient(token)
	if base := os.Getenv("SURF_API_BASE_URL"); base != "" {
		// The SDK adds /v1 internally, so strip it if the env var includes it
		base = strings.TrimRight(base, "/")
		base = strings.TrimSuffix(base, "/v1")
		c.BaseURL = base
	}
	return c
}

// skipOnScope skips the test if the error indicates a missing scope (401 or 403).
func skipOnScope(t *testing.T, err error, msg string) {
	t.Helper()
	if err == nil {
		return
	}
	var apiErr *APIError
	if errors.As(err, &apiErr) && (apiErr.StatusCode == 401 || apiErr.StatusCode == 403) {
		t.Skipf("%s: %v", msg, apiErr)
	}
}

// extractFeedID extracts the feed ULID from the create response, stripping the surf/custom/ prefix.
func extractFeedID(raw json.RawMessage) (string, error) {
	var data map[string]interface{}
	if err := json.Unmarshal(raw, &data); err != nil {
		return "", err
	}
	for _, key := range []string{"id", "surfId", "surf_id"} {
		if v, ok := data[key].(string); ok && v != "" {
			return strings.TrimPrefix(v, "surf/custom/"), nil
		}
	}
	return "", fmt.Errorf("no feed ID found in response: %s", string(raw))
}

// extractPostID extracts the post ID from a create-status response.
func extractPostID(raw json.RawMessage) (string, error) {
	var data map[string]interface{}
	if err := json.Unmarshal(raw, &data); err != nil {
		return "", err
	}
	if v, ok := data["id"].(string); ok && v != "" {
		return v, nil
	}
	return "", fmt.Errorf("no post ID found in response: %s", string(raw))
}

func TestIntegration(t *testing.T) {
	client := testClient(t)

	// =====================================================================
	// 1. Feeds
	// =====================================================================
	t.Run("Feeds", func(t *testing.T) {
		t.Run("GetFeedMetadata", func(t *testing.T) {
			raw, err := client.Feeds.Get("surf/topic/technology")
			if err != nil {
				t.Fatalf("Feeds.Get failed: %v", err)
			}
			var meta FeedMetaTyped
			if err := json.Unmarshal(raw, &meta); err != nil {
				t.Fatalf("Failed to unmarshal feed metadata: %v", err)
			}
			if meta.Title == "" {
				t.Error("Feed should have a title")
			}
			if meta.SurfID != "surf/topic/technology" {
				t.Errorf("Expected surf_id=surf/topic/technology, got %q", meta.SurfID)
			}
		})

		t.Run("GetFeedMissingParam", func(t *testing.T) {
			_, err := client.Feeds.Get("")
			if err == nil {
				t.Fatal("Expected error for missing surf_id")
			}
			var apiErr *APIError
			if errors.As(err, &apiErr) {
				if apiErr.StatusCode != 400 {
					t.Errorf("Expected 400, got %d", apiErr.StatusCode)
				}
			}
		})

		t.Run("GetPostsWithLimit", func(t *testing.T) {
			raw, err := client.Feeds.GetPosts("surf/topic/technology", &PostsOptions{Limit: 5})
			if err != nil {
				t.Fatalf("Feeds.GetPosts failed: %v", err)
			}
			// Response might be an array or an object with a posts key
			var posts []json.RawMessage
			if err := json.Unmarshal(raw, &posts); err != nil {
				var wrapper struct {
					Posts []json.RawMessage `json:"posts"`
					Items []json.RawMessage `json:"items"`
				}
				if err := json.Unmarshal(raw, &wrapper); err != nil {
					t.Fatalf("Failed to parse posts response: %v", err)
				}
				posts = wrapper.Posts
				if len(posts) == 0 {
					posts = wrapper.Items
				}
			}
			if len(posts) == 0 {
				t.Error("Expected at least one post")
			}
			if len(posts) > 5 {
				t.Errorf("Expected at most 5 posts, got %d", len(posts))
			}
		})

		t.Run("GetPostsSortRecent", func(t *testing.T) {
			raw, err := client.Feeds.GetPosts("surf/topic/technology", &PostsOptions{Limit: 3, Sort: "recent"})
			if err != nil {
				t.Fatalf("Feeds.GetPosts(sort=recent) failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty response")
			}
		})
	})

	// =====================================================================
	// 2. Search
	// =====================================================================
	t.Run("Search", func(t *testing.T) {
		t.Run("SearchFeeds", func(t *testing.T) {
			raw, err := client.Search.Feeds("technology", 5)
			if err != nil {
				t.Fatalf("Search.Feeds failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty search results")
			}
		})

		t.Run("SearchPosts", func(t *testing.T) {
			raw, err := client.Search.Posts("artificial intelligence", 5)
			if err != nil {
				t.Fatalf("Search.Posts failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty search results")
			}
		})

		t.Run("SearchAccounts", func(t *testing.T) {
			raw, err := client.Search.Accounts("surf", 5)
			if err != nil {
				t.Fatalf("Search.Accounts failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty search results")
			}
		})

		t.Run("SearchEmptyQuery", func(t *testing.T) {
			_, err := client.Search.Feeds("", 5)
			// Either succeeds (empty results) or returns 400; both are acceptable
			if err != nil {
				var apiErr *APIError
				if errors.As(err, &apiErr) && apiErr.StatusCode != 400 {
					t.Errorf("Expected success or 400, got %d", apiErr.StatusCode)
				}
			}
		})
	})

	// =====================================================================
	// 3. Custom Feeds
	// =====================================================================
	t.Run("CustomFeeds", func(t *testing.T) {
		var feedID string

		t.Run("Create", func(t *testing.T) {
			raw, err := client.CustomFeeds.Create(map[string]string{
				"title":       "Go SDK Test Feed",
				"description": "Automated integration test — safe to delete",
			})
			skipOnScope(t, err, "Token lacks write:feeds scope")
			if err != nil {
				t.Fatalf("CustomFeeds.Create failed: %v", err)
			}
			var e error
			feedID, e = extractFeedID(raw)
			if e != nil {
				t.Fatalf("Could not extract feed ID: %v", e)
			}
			t.Logf("Created custom feed: %s", feedID)
		})

		// Ensure cleanup runs even if subtests fail
		t.Cleanup(func() {
			if feedID == "" {
				return
			}
			t.Logf("Cleanup: deleting feed %s", feedID)
			_ = client.CustomFeeds.Delete(feedID)
		})

		t.Run("AddOperators", func(t *testing.T) {
			if feedID == "" {
				t.Skip("No feed created")
			}
			operators := []struct {
				name string
				op   map[string]string
			}{
				{"topic", map[string]string{"surfId": "surf/topic/technology", "operator": "source"}},
				{"hashtag", map[string]string{"surfId": "surf/hashtag/opensource", "operator": "source"}},
				{"bluesky_user", map[string]string{"surfId": "bluesky/user/@jay.bsky.team", "operator": "source"}},
			}
			for _, tc := range operators {
				t.Run(tc.name, func(t *testing.T) {
					_, err := client.CustomFeeds.AddOperator(feedID, tc.op)
					if err != nil {
						t.Fatalf("AddOperator(%s) failed: %v", tc.name, err)
					}
				})
			}
		})

		t.Run("GetAndVerifyOperators", func(t *testing.T) {
			if feedID == "" {
				t.Skip("No feed created")
			}
			raw, err := client.CustomFeeds.Get(feedID)
			if err != nil {
				t.Fatalf("CustomFeeds.Get failed: %v", err)
			}
			var data struct {
				Operators []struct {
					SurfID   string `json:"surfId"`
					Operator string `json:"operator"`
				} `json:"operators"`
			}
			if err := json.Unmarshal(raw, &data); err != nil {
				t.Fatalf("Failed to parse feed data: %v", err)
			}
			storedIDs := make(map[string]bool)
			for _, op := range data.Operators {
				storedIDs[op.SurfID] = true
			}
			expected := []string{
				"surf/topic/technology",
				"surf/hashtag/opensource",
				"bluesky/user/@jay.bsky.team",
			}
			for _, id := range expected {
				if !storedIDs[id] {
					t.Errorf("Expected operator %q not found in stored operators: %v", id, storedIDs)
				}
			}
		})

		t.Run("ListFeeds", func(t *testing.T) {
			raw, err := client.CustomFeeds.List()
			if err != nil {
				t.Fatalf("CustomFeeds.List failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty feed list")
			}
		})

		t.Run("Delete", func(t *testing.T) {
			if feedID == "" {
				t.Skip("No feed created")
			}
			err := client.CustomFeeds.Delete(feedID)
			if err != nil {
				var apiErr *APIError
				if errors.As(err, &apiErr) && apiErr.StatusCode == 404 {
					// Already deleted, fine
					return
				}
				t.Fatalf("CustomFeeds.Delete failed: %v", err)
			}
			// Mark as deleted so cleanup doesn't double-delete
			feedID = ""
		})
	})

	// =====================================================================
	// 3b. CreateWithOperators typed helper
	// =====================================================================
	t.Run("CreateWithOperators", func(t *testing.T) {
		var feedID string

		t.Run("Create", func(t *testing.T) {
			raw, err := client.CustomFeeds.CreateWithOperators(
				"Go SDK OpTest Feed",
				"CreateWithOperators integration test — safe to delete",
				NewFeedOperatorSource("surf/topic/technology"),
				NewFeedOperatorSource("surf/hashtag/opensource"),
			)
			skipOnScope(t, err, "Token lacks write:feeds scope")
			if err != nil {
				t.Fatalf("CreateWithOperators failed: %v", err)
			}
			var e error
			feedID, e = extractFeedID(raw)
			if e != nil {
				t.Fatalf("Could not extract feed ID: %v", e)
			}
			t.Logf("Created OpTest feed: %s", feedID)
		})

		t.Cleanup(func() {
			if feedID != "" {
				t.Logf("Cleanup: deleting OpTest feed %s", feedID)
				_ = client.CustomFeeds.Delete(feedID)
			}
		})

		t.Run("VerifyOperators", func(t *testing.T) {
			if feedID == "" {
				t.Skip("No feed created")
			}
			raw, err := client.CustomFeeds.Get(feedID)
			if err != nil {
				t.Fatalf("CustomFeeds.Get failed: %v", err)
			}
			var data struct {
				Operators []struct {
					SurfID string `json:"surfId"`
				} `json:"operators"`
			}
			if err := json.Unmarshal(raw, &data); err != nil {
				t.Fatalf("Failed to parse feed data: %v", err)
			}
			storedIDs := make(map[string]bool)
			for _, op := range data.Operators {
				storedIDs[op.SurfID] = true
			}
			for _, id := range []string{"surf/topic/technology", "surf/hashtag/opensource"} {
				if !storedIDs[id] {
					t.Errorf("Expected operator %q not found, got: %v", id, storedIDs)
				}
			}
		})
	})

	// =====================================================================
	// 3c. Custom Feed Themes
	// =====================================================================
	t.Run("CustomFeedThemes", func(t *testing.T) {
		var feedID string

		t.Run("CreateWithTheme", func(t *testing.T) {
			theme := FeedTheme{
				Header: &FeedThemeHeader{
					Image:     "https://surf.social/img/surf-logo.png",
					ImageSize: map[string]interface{}{"width": 600, "height": 272},
				},
				Colors: &FeedThemeColors{
					Light: map[string]string{"surface": "#EFEADD", "surfaceHeader": "#005F5F"},
				},
			}
			raw, err := client.CustomFeeds.Create(map[string]interface{}{
				"title":       "Go SDK Theme Test",
				"description": "Automated theme test — safe to delete",
				"theme":       theme.ToMap(),
			})
			skipOnScope(t, err, "Token lacks write:feeds scope")
			if err != nil {
				t.Fatalf("CustomFeeds.Create with theme failed: %v", err)
			}
			var e error
			feedID, e = extractFeedID(raw)
			if e != nil {
				t.Fatalf("Could not extract feed ID: %v", e)
			}
			// Verify theme in response
			var resp map[string]interface{}
			if err := json.Unmarshal(raw, &resp); err != nil {
				t.Fatalf("Failed to parse response: %v", err)
			}
			themeResp, ok := resp["theme"].(map[string]interface{})
			if !ok {
				t.Fatal("Response should include theme object")
			}
			header, _ := themeResp["header"].(map[string]interface{})
			if header == nil || header["image"] != "https://surf.social/img/surf-logo.png" {
				t.Errorf("Expected header image in response, got: %v", header)
			}
		})

		t.Cleanup(func() {
			if feedID == "" {
				return
			}
			_ = client.CustomFeeds.Delete(feedID)
		})

		t.Run("GetTheme", func(t *testing.T) {
			if feedID == "" {
				t.Skip("No themed feed created")
			}
			raw, err := client.CustomFeeds.Get(feedID)
			if err != nil {
				t.Fatalf("GET failed: %v", err)
			}
			var resp map[string]interface{}
			if err := json.Unmarshal(raw, &resp); err != nil {
				t.Fatalf("Failed to parse: %v", err)
			}
			if resp["theme"] == nil {
				t.Fatal("GET response should include theme")
			}
		})

		t.Run("Delete", func(t *testing.T) {
			if feedID == "" {
				t.Skip("No themed feed created")
			}
			err := client.CustomFeeds.Delete(feedID)
			if err != nil {
				var apiErr *APIError
				if errors.As(err, &apiErr) && apiErr.StatusCode == 404 {
					return
				}
				t.Fatalf("Delete failed: %v", err)
			}
			feedID = ""
		})
	})

	// =====================================================================
	// 4. Write Ops (Mastodon)
	// =====================================================================
	t.Run("WriteOpsMastodon", func(t *testing.T) {
		var postID string

		t.Run("CreatePost", func(t *testing.T) {
			status := fmt.Sprintf("Go SDK test (mastodon) — %d. Safe to delete.", time.Now().Unix())
			raw, err := client.Feeds.CreatePost(status, "public", "mastodon")
			skipOnScope(t, err, "No mastodon linked account or missing write scope")
			if err != nil {
				t.Fatalf("CreatePost(mastodon) failed: %v", err)
			}
			var e error
			postID, e = extractPostID(raw)
			if e != nil {
				t.Fatalf("Could not extract post ID: %v", e)
			}
			t.Logf("Created mastodon post: %s", postID)
		})

		t.Cleanup(func() {
			if postID == "" {
				return
			}
			t.Logf("Cleanup: deleting mastodon post %s", postID)
			_ = client.Feeds.DeletePost(postID, "mastodon")
		})

		t.Run("Favourite", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			_, err := client.Feeds.Favourite(postID, "mastodon")
			if err != nil {
				t.Fatalf("Favourite failed: %v", err)
			}
		})

		t.Run("Unfavourite", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			_, err := client.Feeds.Unfavourite(postID, "mastodon")
			if err != nil {
				t.Fatalf("Unfavourite failed: %v", err)
			}
		})

		t.Run("Bookmark", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			_, err := client.Feeds.Bookmark(postID, "mastodon")
			// Bookmark has no AT Protocol equivalent (the Bluesky bridge
			// doesn't implement it), so a Bluesky-backed account 404s. Skip
			// rather than fail; bookmark works for native Mastodon accounts.
			var apiErr *APIError
			if errors.As(err, &apiErr) && apiErr.StatusCode == 404 {
				t.Skip("Bookmark not supported for Bluesky-backed posts")
			}
			if err != nil {
				t.Fatalf("Bookmark failed: %v", err)
			}
		})

		t.Run("Unbookmark", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			_, err := client.Feeds.Unbookmark(postID, "mastodon")
			var apiErr *APIError
			if errors.As(err, &apiErr) && apiErr.StatusCode == 404 {
				t.Skip("Unbookmark not supported for Bluesky-backed posts")
			}
			if err != nil {
				t.Fatalf("Unbookmark failed: %v", err)
			}
		})

		t.Run("DeletePost", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			err := client.Feeds.DeletePost(postID, "mastodon")
			if err != nil {
				t.Fatalf("DeletePost failed: %v", err)
			}
			postID = "" // prevent cleanup double-delete
		})
	})

	// =====================================================================
	// 5. Write Ops (Bluesky)
	// =====================================================================
	t.Run("WriteOpsBluesky", func(t *testing.T) {
		var postID string

		t.Run("CreatePost", func(t *testing.T) {
			status := fmt.Sprintf("Go SDK test (bluesky) — %d. Safe to delete.", time.Now().Unix())
			raw, err := client.Feeds.CreatePost(status, "public", "bluesky")
			skipOnScope(t, err, "No bluesky linked account or missing write scope")
			if err != nil {
				t.Fatalf("CreatePost(bluesky) failed: %v", err)
			}
			var e error
			postID, e = extractPostID(raw)
			if e != nil {
				t.Fatalf("Could not extract post ID: %v", e)
			}
			t.Logf("Created bluesky post: %s", postID)
		})

		t.Cleanup(func() {
			if postID == "" {
				return
			}
			t.Logf("Cleanup: deleting bluesky post %s", postID)
			_ = client.Feeds.DeletePost(postID, "bluesky")
		})

		t.Run("Favourite", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			_, err := client.Feeds.Favourite(postID, "bluesky")
			if err != nil {
				t.Fatalf("Favourite failed: %v", err)
			}
		})

		t.Run("DeletePost", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			err := client.Feeds.DeletePost(postID, "bluesky")
			if err != nil {
				t.Fatalf("DeletePost failed: %v", err)
			}
			postID = ""
		})
	})

	// =====================================================================
	// 6. AI
	// =====================================================================
	t.Run("AI", func(t *testing.T) {
		t.Run("Ask", func(t *testing.T) {
			raw, err := client.AI.Ask("What is happening in technology today?", 3)
			skipOnScope(t, err, "Token lacks use:ai scope")
			if err != nil {
				// AI rate limit is 10/day — if we hit it, skip rather than fail
				var apiErr *APIError
				if errors.As(err, &apiErr) && apiErr.StatusCode == 429 {
					t.Skip("AI rate limit exceeded (10/day)")
				}
				t.Fatalf("AI.Ask failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty AI response")
			}
		})

		t.Run("FeedSummary", func(t *testing.T) {
			raw, err := client.AI.FeedSummary("surf/topic/technology", 10)
			skipOnScope(t, err, "Token lacks use:ai scope")
			if err != nil {
				var apiErr *APIError
				if errors.As(err, &apiErr) && apiErr.StatusCode == 429 {
					t.Skip("AI rate limit exceeded (10/day)")
				}
				t.Fatalf("AI.FeedSummary failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty feed summary")
			}
		})

		// Media — AI image generation. Gated: GPU-bound (20-60s) and burns the
		// 20/day image quota, so it only runs when SURF_RUN_AI_IMAGE_TESTS=1.
		t.Run("GenerateImage", func(t *testing.T) {
			if os.Getenv("SURF_RUN_AI_IMAGE_TESTS") != "1" {
				t.Skip("set SURF_RUN_AI_IMAGE_TESTS=1 to run (consumes the 20/day GPU image quota, 20-60s)")
			}
			// Submit only (async): validates the {key, url, status} contract without
			// burning ~90s polling for the image.
			raw, err := client.Media.GenerateImage("a calm minimalist landscape, soft pastels", true)
			skipOnScope(t, err, "Token lacks use:ai scope")
			if err != nil {
				var apiErr *APIError
				if errors.As(err, &apiErr) && (apiErr.StatusCode == 429 || apiErr.StatusCode == 502 || apiErr.StatusCode == 503) {
					t.Skipf("image generation unavailable (HTTP %d)", apiErr.StatusCode)
				}
				t.Fatalf("Media.GenerateImage failed: %v", err)
			}
			var job struct {
				Key    string `json:"key"`
				URL    string `json:"url"`
				Status string `json:"status"`
			}
			if err := json.Unmarshal(raw, &job); err != nil {
				t.Fatalf("Failed to parse submit response: %v", err)
			}
			if job.Key == "" || job.URL == "" {
				t.Error("Expected key and url in submit response")
			}
			if job.Status != "pending" {
				t.Errorf("Expected status pending, got %q", job.Status)
			}
		})
	})

	// =====================================================================
	// 6b. Paginator
	// =====================================================================
	t.Run("Paginator", func(t *testing.T) {
		t.Run("RespectsLimit", func(t *testing.T) {
			// Paginate() targets object-response endpoints ({"key": [...], "cursor": "..."}).
			// /feed/posts may return a bare JSON array on some server configs.
			// In that case Next() returns false with a parse error — acceptable behavior.
			pager := client.Paginate("/feed/posts", "posts",
				url.Values{"surf_id": {"surf/topic/technology"}, "limit": {"2"}}, 4)
			var items []json.RawMessage
			for pager.Next() {
				items = append(items, pager.Item())
			}
			if err := pager.Err(); err != nil {
				if isBareArrayError(err) {
					t.Skipf("Paginator skipped: endpoint returned a bare array (paginate() requires an object response): %v", err)
				}
				t.Fatalf("Paginator unexpected error: %v", err)
			}
			if len(items) > 4 {
				t.Errorf("limit=4 must cap results, got %d", len(items))
			}
			t.Logf("Paginator yielded %d item(s)", len(items))
		})

		t.Run("MissingKeyYieldsNothing", func(t *testing.T) {
			// A key absent from the response must yield 0 items without error
			// (assuming the endpoint returns an object; bare-array endpoints
			// produce a parse error which we log and skip).
			pager := client.Paginate("/feed/posts", "nonexistent_key_xyz",
				url.Values{"surf_id": {"surf/topic/technology"}}, 0)
			count := 0
			for pager.Next() {
				pager.Item()
				count++
			}
			if err := pager.Err(); err != nil {
				if isBareArrayError(err) {
					t.Skipf("Paginator skipped: endpoint returned a bare array (paginate() requires an object response): %v", err)
				}
				t.Fatalf("Paginator unexpected error: %v", err)
			}
			if count != 0 {
				t.Errorf("missing key should yield 0 items, got %d", count)
			}
		})
	})

	// =====================================================================
	// 7. Error Handling
	// =====================================================================
	t.Run("ErrorHandling", func(t *testing.T) {
		t.Run("InvalidToken", func(t *testing.T) {
			badClient := NewClient("invalid_token_xxx")
			if base := os.Getenv("SURF_API_BASE_URL"); base != "" {
				base = strings.TrimRight(base, "/")
				base = strings.TrimSuffix(base, "/v1")
				badClient.BaseURL = base
			}
			_, err := badClient.Feeds.Get("surf/topic/technology")
			if err == nil {
				t.Fatal("Expected error with invalid token")
			}
			var apiErr *APIError
			if !errors.As(err, &apiErr) {
				t.Fatalf("Expected *APIError, got %T: %v", err, err)
			}
			if apiErr.StatusCode != 401 && apiErr.StatusCode != 403 {
				t.Errorf("Expected 401 or 403, got %d", apiErr.StatusCode)
			}
		})

		t.Run("APIErrorType", func(t *testing.T) {
			// Verify APIError implements the error interface and errors.As works
			_, err := client.Feeds.Get("")
			if err == nil {
				// Some servers may accept empty string; that's OK
				return
			}
			var apiErr *APIError
			if !errors.As(err, &apiErr) {
				t.Fatalf("Expected *APIError for bad request, got %T: %v", err, err)
			}
			if apiErr.StatusCode == 0 {
				t.Error("APIError.StatusCode should be non-zero")
			}
			// Verify Error() string is non-empty
			if apiErr.Error() == "" {
				t.Error("APIError.Error() should return a non-empty string")
			}
		})

		t.Run("RateLimitHeaders", func(t *testing.T) {
			// After any successful request, RateLimit should be populated
			_, _ = client.Feeds.Get("surf/topic/technology")
			if client.RateLimit == nil {
				t.Skip("Server did not return rate limit headers")
			}
			if client.RateLimit.Limit <= 0 {
				t.Logf("Warning: RateLimit.Limit=%d (may not be set by server)", client.RateLimit.Limit)
			}
		})

		t.Run("ServiceParamValidation", func(t *testing.T) {
			// Passing 2+ service values must return an error, not panic.
			_, err := client.Feeds.Favourite("any-id", "bluesky", "mastodon")
			if err == nil {
				t.Fatal("Expected error when 2 service values provided, got nil")
			}
			if !strings.Contains(err.Error(), "at most one service value") {
				t.Errorf("Unexpected error message: %v", err)
			}

			// Omitting service entirely must not error at the validation layer.
			// Use a read-only call so no post is created; network/auth errors are fine —
			// we only care that svcParams does not reject a zero-length service slice.
			_, err = client.Feeds.Get("surf/topic/technology")
			if err != nil && strings.Contains(err.Error(), "at most one service value") {
				t.Errorf("Omitting service should not trigger validation error, got: %v", err)
			}
		})
	})
}

// rtbTestClient returns a configured RTBClient, skipping the test if
// SURF_API_TEST_TOKEN is not set (the same env token the other integration
// tests use). The RTB base URL is surf.social; the SDK appends
// /devportal/v1/rtb internally. SURF_API_BASE_URL, if set, overrides the host
// (any trailing /v1 is stripped, matching testClient).
func rtbTestClient(t *testing.T) *RTBClient {
	t.Helper()
	token := os.Getenv("SURF_API_TEST_TOKEN")
	if token == "" {
		t.Skip("SURF_API_TEST_TOKEN not set")
	}
	c := NewRTBClient(token)
	if base := os.Getenv("SURF_API_BASE_URL"); base != "" {
		base = strings.TrimRight(base, "/")
		base = strings.TrimSuffix(base, "/v1")
		c.BaseURL = base
	}
	return c
}

func TestRTBIntegration(t *testing.T) {
	client := rtbTestClient(t)

	// =====================================================================
	// 1. Sandbox bid — sandbox=true sets test=1, needs no publisher config
	//    and never spends. A minimal OpenRTB 2.5 bid request is sufficient.
	// =====================================================================
	t.Run("SandboxBid", func(t *testing.T) {
		req := map[string]interface{}{
			"id": fmt.Sprintf("go-sdk-test-%d", time.Now().Unix()),
			"imp": []map[string]interface{}{
				{
					"id": "1",
					"banner": map[string]interface{}{
						"w": 300,
						"h": 250,
					},
				},
			},
			"site": map[string]interface{}{
				"page": "https://example.com/test",
			},
		}
		raw, err := client.Bid(req, true)
		skipOnScope(t, err, "Token lacks rtb:bid scope")
		if err != nil {
			// A sandbox bid may legitimately return 204/no-bid surfaced as an
			// empty body; only fail on a real error.
			t.Fatalf("RTB sandbox Bid failed: %v", err)
		}
		t.Logf("RTB sandbox bid returned %d bytes", len(raw))
	})

	// =====================================================================
	// 2. Reports
	// =====================================================================
	t.Run("Reports", func(t *testing.T) {
		raw, err := client.Reports(7, "day")
		skipOnScope(t, err, "Token lacks rtb:reports scope")
		if err != nil {
			t.Fatalf("RTB Reports failed: %v", err)
		}
		if len(raw) == 0 {
			t.Error("Expected non-empty reports response")
		}
	})

	// =====================================================================
	// 3. Config
	// =====================================================================
	t.Run("Config", func(t *testing.T) {
		raw, err := client.Config()
		skipOnScope(t, err, "Token lacks RTB config access")
		if err != nil {
			// The account may not be a registered RTB publisher; the API
			// correctly returns 503 "could not be initialized" in that case.
			var apiErr *APIError
			if errors.As(err, &apiErr) && apiErr.StatusCode == 503 {
				t.Skipf("Account has no RTB publisher config: %v", apiErr)
			}
			t.Fatalf("RTB Config failed: %v", err)
		}
		if len(raw) == 0 {
			t.Error("Expected non-empty config response")
		}
	})

	// =====================================================================
	// 4. Scopes
	// =====================================================================
	t.Run("Scopes", func(t *testing.T) {
		raw, err := client.Scopes()
		skipOnScope(t, err, "Token lacks RTB scopes access")
		if err != nil {
			t.Fatalf("RTB Scopes failed: %v", err)
		}
		if len(raw) == 0 {
			t.Error("Expected non-empty scopes response")
		}
	})

	// =====================================================================
	// 5. AdsTxt
	// =====================================================================
	t.Run("AdsTxt", func(t *testing.T) {
		raw, err := client.AdsTxt()
		skipOnScope(t, err, "Token lacks RTB ads.txt access")
		if err != nil {
			t.Fatalf("RTB AdsTxt failed: %v", err)
		}
		if len(raw) == 0 {
			t.Error("Expected non-empty ads.txt response")
		}
	})

	// =====================================================================
	// 6. Error handling — an invalid token must yield a typed *APIError
	//    carrying the HTTP status code (401/403).
	// =====================================================================
	t.Run("InvalidToken", func(t *testing.T) {
		bad := NewRTBClient("invalid_token_xxx")
		if base := os.Getenv("SURF_API_BASE_URL"); base != "" {
			base = strings.TrimRight(base, "/")
			base = strings.TrimSuffix(base, "/v1")
			bad.BaseURL = base
		}
		_, err := bad.Config()
		if err == nil {
			t.Fatal("Expected error with invalid RTB token")
		}
		var apiErr *APIError
		if !errors.As(err, &apiErr) {
			t.Fatalf("Expected *APIError, got %T: %v", err, err)
		}
		if apiErr.StatusCode != 401 && apiErr.StatusCode != 403 {
			t.Errorf("Expected 401 or 403, got %d", apiErr.StatusCode)
		}
	})
}
