package surf

import (
	"encoding/json"
	"testing"
)

// The graded content-safety verdict on a Post: field names shared with REST/MCP/the
// other SDKs, the open label vocabulary, and defaults that must never turn "no signal"
// into "checked and clean".
// See services/specs/brand_safety/CONTENT_SAFETY_CLASSIFICATION.md sections 2 and 7.

func TestPostSafetyDecodesGradedVerdict(t *testing.T) {
	var post Post
	body := `{"id":"1","safety":{"rating":"explicit","labels":["porn"],"source":"self-label"}}`
	if err := json.Unmarshal([]byte(body), &post); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if post.Safety == nil {
		t.Fatal("Safety is nil")
	}
	if post.Safety.Rating != "explicit" {
		t.Errorf("Rating = %q, want explicit", post.Safety.Rating)
	}
	if len(post.Safety.Labels) != 1 || post.Safety.Labels[0] != "porn" {
		t.Errorf("Labels = %v, want [porn]", post.Safety.Labels)
	}
	if post.Safety.Source != "self-label" {
		t.Errorf("Source = %q, want self-label", post.Safety.Source)
	}
}

func TestPostSafetyAbsentStaysNil(t *testing.T) {
	var post Post
	if err := json.Unmarshal([]byte(`{"id":"1"}`), &post); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if post.Safety != nil {
		t.Errorf("Safety = %+v, want nil when the server sent no verdict", post.Safety)
	}
}

func TestPostSafetyUnknownVerdictHasNoLabels(t *testing.T) {
	var post Post
	// The server omits `labels` entirely when nothing was observed.
	body := `{"id":"1","safety":{"rating":"unknown","source":"none"}}`
	if err := json.Unmarshal([]byte(body), &post); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if post.Safety.Rating != "unknown" || post.Safety.Source != "none" {
		t.Errorf("got %+v, want unknown/none", post.Safety)
	}
	if post.Safety.Labels != nil {
		t.Errorf("Labels = %v, want nil", post.Safety.Labels)
	}
}

func TestPostSafetyCarriesUnrecognizedLabels(t *testing.T) {
	var post Post
	// Open vocabulary: a future labeler value survives the trip.
	body := `{"id":"1","safety":{"rating":"explicit","labels":["porn","some-future-label"],"source":"bsky-moderation"}}`
	if err := json.Unmarshal([]byte(body), &post); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(post.Safety.Labels) != 2 || post.Safety.Labels[1] != "some-future-label" {
		t.Errorf("Labels = %v, want both values carried", post.Safety.Labels)
	}
}

func TestPostSafetyOnNestedReblog(t *testing.T) {
	var post Post
	body := `{"id":"1","reblog":{"id":"2","safety":{"rating":"suggestive","source":"self-label"}}}`
	if err := json.Unmarshal([]byte(body), &post); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if post.Reblog == nil || post.Reblog.Safety == nil {
		t.Fatal("reblog verdict missing")
	}
	if post.Reblog.Safety.Rating != "suggestive" {
		t.Errorf("Rating = %q, want suggestive", post.Reblog.Safety.Rating)
	}
}

func TestPostSafetyMarshalsRatingAndSourceAlways(t *testing.T) {
	// rating/source are not omitempty: a consumer never has to tell "field missing"
	// from "no signal".
	out, err := json.Marshal(&PostSafety{Rating: "unknown", Source: "none"})
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if string(out) != `{"rating":"unknown","source":"none"}` {
		t.Errorf("got %s", out)
	}
}
