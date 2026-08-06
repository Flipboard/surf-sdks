"""Unit tests that the feed `since` (recency window) param is threaded into the
`/feed/posts` request for both the sync and async clients. No live API required.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from surf_api.client import _FeedsAPI
from surf_api.async_client import _AsyncFeedsAPI


class _FakeClient:
    """Captures (path, params) for a sync _get."""
    def __init__(self):
        self.calls = []

    def _get(self, path, params=None):
        self.calls.append((path, params))
        return []


class _FakeAsyncClient:
    """Captures (path, params) for an async _get."""
    def __init__(self):
        self.calls = []

    async def _get(self, path, params=None):
        self.calls.append((path, params))
        return []


class TestSyncSince:
    def test_get_posts_threads_since(self):
        c = _FakeClient()
        _FeedsAPI(c).get_posts("surf/topic/technology", limit=5, since="24h")
        path, params = c.calls[0]
        assert path == "/feed/posts"
        assert params["surf_id"] == "surf/topic/technology"
        assert params["limit"] == 5
        assert params["since"] == "24h"

    def test_get_posts_since_defaults_none(self):
        c = _FakeClient()
        _FeedsAPI(c).get_posts("surf/topic/technology")
        _path, params = c.calls[0]
        assert params["since"] is None

    def test_get_posts_accepts_iso_timestamp(self):
        c = _FakeClient()
        _FeedsAPI(c).get_posts("surf/topic/technology", since="2026-01-01T00:00:00Z")
        _path, params = c.calls[0]
        assert params["since"] == "2026-01-01T00:00:00Z"


class TestAsyncSince:
    def test_get_posts_threads_since(self):
        c = _FakeAsyncClient()
        asyncio.run(_AsyncFeedsAPI(c).get_posts("surf/topic/technology", limit=5, since="7d"))
        path, params = c.calls[0]
        assert path == "/feed/posts"
        assert params["surf_id"] == "surf/topic/technology"
        assert params["limit"] == 5
        assert params["since"] == "7d"

    def test_get_posts_since_defaults_none(self):
        c = _FakeAsyncClient()
        asyncio.run(_AsyncFeedsAPI(c).get_posts("surf/topic/technology"))
        _path, params = c.calls[0]
        assert params["since"] is None
