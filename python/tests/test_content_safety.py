"""Unit tests for the graded content-safety verdict on Post — no live API required.

Covers PostSafety parsing off an API post: the field names REST/MCP/SDKs share, the
open label vocabulary, and the defaults, which must never turn "no signal" into
"checked and clean".
See services/specs/brand_safety/CONTENT_SAFETY_CLASSIFICATION.md sections 2 and 7.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from surf_api.models import Post, PostSafety


class TestPostSafety:
    def test_parses_graded_verdict(self):
        post = Post.from_dict({
            "id": "1",
            "safety": {"rating": "explicit", "labels": ["porn"], "source": "self-label"},
        })
        assert isinstance(post.safety, PostSafety)
        assert post.safety.rating == "explicit"
        assert post.safety.labels == ["porn"]
        assert post.safety.source == "self-label"

    def test_suggestive_tier(self):
        post = Post.from_dict({
            "id": "1",
            "safety": {"rating": "suggestive", "labels": ["nudity"], "source": "bsky-moderation"},
        })
        assert post.safety.rating == "suggestive"
        assert post.safety.source == "bsky-moderation"

    def test_absent_safety_is_none(self):
        # Older servers, or any response predating the field: nothing is fabricated.
        assert Post.from_dict({"id": "1"}).safety is None

    def test_unknown_verdict_carries_no_labels(self):
        # The server omits `labels` entirely when nothing was observed.
        post = Post.from_dict({"id": "1", "safety": {"rating": "unknown", "source": "none"}})
        assert post.safety.rating == "unknown"
        assert post.safety.labels is None
        assert post.safety.source == "none"

    def test_partial_verdict_defaults_to_unknown_not_safe(self):
        post = Post.from_dict({"id": "1", "safety": {"labels": ["bot"]}})
        assert post.safety.rating == "unknown"
        assert post.safety.source == "none"
        assert post.safety.labels == ["bot"]

    def test_unrecognized_label_values_are_carried(self):
        # Open vocabulary: a future labeler value survives the trip.
        post = Post.from_dict({
            "id": "1",
            "safety": {"rating": "explicit", "labels": ["porn", "some-future-label"],
                       "source": "bsky-moderation"},
        })
        assert post.safety.labels == ["porn", "some-future-label"]

    def test_verdict_on_nested_reblog_and_quote(self):
        post = Post.from_dict({
            "id": "1",
            "reblog": {"id": "2", "safety": {"rating": "explicit", "source": "self-label"}},
            "quote": {"id": "3", "safety": {"rating": "suggestive", "source": "self-label"}},
        })
        assert post.reblog.safety.rating == "explicit"
        assert post.quote.safety.rating == "suggestive"

    def test_exported_from_package_root(self):
        import surf_api
        assert surf_api.PostSafety is PostSafety
