"""Unit tests for search type→endpoint routing — no live API required."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from surf_api.client import _SearchAPI


class _FakeClient:
    """Captures the (path, params) that _SearchAPI would call."""
    def __init__(self):
        self.calls = []

    def _get(self, path, params=None):
        self.calls.append((path, params))
        return {"ok": True}


def _api():
    return _SearchAPI(_FakeClient())


class TestSearchRouting:
    def test_posts_routes_to_search_posts_with_sort(self):
        api = _api()
        api.search("cyberpunk", type="posts", sort="recent")
        path, params = api._c.calls[0]
        assert path == "/search/posts"
        assert params == {"q": "cyberpunk", "limit": 20, "sort": "recent"}

    def test_feeds_routes_to_maestra_no_type_param(self):
        api = _api()
        api.search("tech", type="feeds")
        path, params = api._c.calls[0]
        assert path == "/search/maestra/feeds"
        assert "type" not in params and "sort" not in params

    def test_accounts_routes_to_bluesky_actors(self):
        api = _api()
        api.search("someone", type="accounts")
        assert api._c.calls[0][0] == "/search/bluesky/searchActors"

    def test_podcasts_maps_to_maestra(self):
        api = _api()
        api.search("news", type="podcasts")
        assert api._c.calls[0][0] == "/search/maestra/feeds"

    def test_rss_routes_to_rss_search(self):
        api = _api()
        api.search("blog", type="rss")
        assert api._c.calls[0][0] == "/search/rss/search"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            _api().search("x", type="bogus")

    def test_posts_helper_passes_sort_through(self):
        api = _api()
        api.posts("cyberpunk", sort="recent")
        path, params = api._c.calls[0]
        assert path == "/search/posts"
        assert params.get("sort") == "recent"

    def test_posts_without_sort_omits_param(self):
        api = _api()
        api.search("cyberpunk", type="posts")
        assert "sort" not in api._c.calls[0][1]
