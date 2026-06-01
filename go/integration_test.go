//go:build integration

package surf

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"
)

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

// retryOnRateLimit executes fn and retries once after sleeping if it returns a 429.
func retryOnRateLimit(t *testing.T, fn func() error) error {
	t.Helper()
	err := fn()
	if err == nil {
		return nil
	}
	var apiErr *APIError
	if errors.As(err, &apiErr) && apiErr.StatusCode == 429 {
		t.Log("Rate limited, sleeping 60s before retry...")
		time.Sleep(60 * time.Second)
		return fn()
	}
	return err
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.Feeds.Get("surf/topic/technology")
				return e
			})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.Feeds.GetPosts("surf/topic/technology", &PostsOptions{Limit: 5})
				return e
			})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.Feeds.GetPosts("surf/topic/technology", &PostsOptions{Limit: 3, Sort: "recent"})
				return e
			})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.Search.Feeds("technology", 5)
				return e
			})
			if err != nil {
				t.Fatalf("Search.Feeds failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty search results")
			}
		})

		t.Run("SearchPosts", func(t *testing.T) {
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.Search.Posts("artificial intelligence", 5)
				return e
			})
			if err != nil {
				t.Fatalf("Search.Posts failed: %v", err)
			}
			if len(raw) == 0 {
				t.Error("Expected non-empty search results")
			}
		})

		t.Run("SearchAccounts", func(t *testing.T) {
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.Search.Accounts("surf", 5)
				return e
			})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.CustomFeeds.Create(map[string]string{
					"title":       "Go SDK Test Feed",
					"description": "Automated integration test — safe to delete",
				})
				return e
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
					err := retryOnRateLimit(t, func() error {
						_, e := client.CustomFeeds.AddOperator(feedID, tc.op)
						return e
					})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.CustomFeeds.Get(feedID)
				return e
			})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.CustomFeeds.List()
				return e
			})
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
			err := retryOnRateLimit(t, func() error {
				return client.CustomFeeds.Delete(feedID)
			})
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
	// 4. Write Ops (Mastodon)
	// =====================================================================
	t.Run("WriteOpsMastodon", func(t *testing.T) {
		var postID string

		t.Run("CreatePost", func(t *testing.T) {
			status := fmt.Sprintf("Go SDK test (mastodon) — %d. Safe to delete.", time.Now().Unix())
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.Feeds.CreatePost(status, "public", "mastodon")
				return e
			})
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
			err := retryOnRateLimit(t, func() error {
				_, e := client.Feeds.Favourite(postID, "mastodon")
				return e
			})
			if err != nil {
				t.Fatalf("Favourite failed: %v", err)
			}
		})

		t.Run("Unfavourite", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			err := retryOnRateLimit(t, func() error {
				_, e := client.Feeds.Unfavourite(postID, "mastodon")
				return e
			})
			if err != nil {
				t.Fatalf("Unfavourite failed: %v", err)
			}
		})

		t.Run("Bookmark", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			err := retryOnRateLimit(t, func() error {
				_, e := client.Feeds.Bookmark(postID, "mastodon")
				return e
			})
			if err != nil {
				t.Fatalf("Bookmark failed: %v", err)
			}
		})

		t.Run("Unbookmark", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			err := retryOnRateLimit(t, func() error {
				_, e := client.Feeds.Unbookmark(postID, "mastodon")
				return e
			})
			if err != nil {
				t.Fatalf("Unbookmark failed: %v", err)
			}
		})

		t.Run("DeletePost", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			err := retryOnRateLimit(t, func() error {
				return client.Feeds.DeletePost(postID, "mastodon")
			})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.Feeds.CreatePost(status, "public", "bluesky")
				return e
			})
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
			err := retryOnRateLimit(t, func() error {
				_, e := client.Feeds.Favourite(postID, "bluesky")
				return e
			})
			if err != nil {
				t.Fatalf("Favourite failed: %v", err)
			}
		})

		t.Run("DeletePost", func(t *testing.T) {
			if postID == "" {
				t.Skip("No post created")
			}
			err := retryOnRateLimit(t, func() error {
				return client.Feeds.DeletePost(postID, "bluesky")
			})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.AI.Ask("What is happening in technology today?", 3)
				return e
			})
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
			var raw json.RawMessage
			err := retryOnRateLimit(t, func() error {
				var e error
				raw, e = client.AI.FeedSummary("surf/topic/technology", 10)
				return e
			})
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
	})
}
