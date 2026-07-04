"""Unit tests for _AIAPI request building — no live API required."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from surf_api.client import _AIAPI


class _FakeClient:
    """Captures the (path, json) that _AIAPI would POST."""
    def __init__(self, response=None):
        self.calls = []
        self._response = response or {}

    def _post(self, path, json=None, **kwargs):
        self.calls.append((path, json))
        return self._response


def _api(response=None):
    return _AIAPI(_FakeClient(response))


class TestFactCheck:
    def test_text_only_posts_camelcase_body(self):
        api = _api()
        api.fact_check(text="The sky is blue.")
        path, body = api._c.calls[0]
        assert path == "/ai/fact-check"
        assert body == {"text": "The sky is blue."}

    def test_post_surf_id_maps_to_camelcase(self):
        api = _api()
        api.fact_check(post_surf_id="surf/post/abc")
        path, body = api._c.calls[0]
        assert path == "/ai/fact-check"
        assert body == {"postSurfId": "surf/post/abc"}

    def test_feed_id_included_when_provided(self):
        api = _api()
        api.fact_check(text="claim", feed_id="surf/topic/tech")
        _, body = api._c.calls[0]
        assert body == {"text": "claim", "feedId": "surf/topic/tech"}

    def test_omits_unprovided_keys(self):
        api = _api()
        api.fact_check(text="claim")
        _, body = api._c.calls[0]
        assert "postSurfId" not in body and "feedId" not in body

    def test_returns_parsed_response(self):
        sample = {
            "postSurfId": None,
            "verdict": "TRUE",
            "answer": "Yes.",
            "paragraphs": [{"text": "Yes.", "citationIndices": [0]}],
            "citations": [{"type": "web", "url": "http://x", "surfId": None}],
        }
        api = _api(sample)
        result = api.fact_check(text="claim")
        assert result == sample

    def test_requires_exactly_one_input(self):
        api = _api()
        with pytest.raises(ValueError):
            api.fact_check()
        with pytest.raises(ValueError):
            api.fact_check(text="a", post_surf_id="surf/post/abc")
        # No request should have been made for the invalid calls.
        assert api._c.calls == []
