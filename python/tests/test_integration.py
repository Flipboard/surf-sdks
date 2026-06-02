"""Surf Python SDK integration tests.

Tests the SDK client against the live API. Requires SURF_API_TEST_TOKEN env var.
"""

import time
import pytest

from surf_api import SurfClient
from surf_api.exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def retry_on_rate_limit(fn):
    """Call fn(), retry once after sleeping if rate limited."""
    try:
        return fn()
    except SurfRateLimitError as e:
        wait = int(e.retry_after) if e.retry_after else 60
        wait = min(wait, 65)
        time.sleep(wait)
        return fn()


# ---------------------------------------------------------------------------
# Feeds
# ---------------------------------------------------------------------------

class TestFeeds:
    def test_get_feed(self, client):
        feed = retry_on_rate_limit(lambda: client.feeds.get("surf/topic/technology"))
        assert feed is not None
        assert "title" in feed or "spoiler_text" in feed

    def test_get_posts(self, client):
        posts = retry_on_rate_limit(lambda: client.feeds.get_posts("surf/topic/technology", limit=5))
        assert isinstance(posts, list)
        assert len(posts) <= 5

    def test_get_posts_with_sort(self, client):
        posts = retry_on_rate_limit(lambda: client.feeds.get_posts("surf/topic/technology", limit=3, sort="recent"))
        assert isinstance(posts, list)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_feeds(self, client):
        results = retry_on_rate_limit(lambda: client.search.feeds("technology"))
        assert results is not None

    def test_search_posts(self, client):
        results = retry_on_rate_limit(lambda: client.search.posts("technology"))
        assert results is not None

    def test_search_accounts(self, client):
        results = retry_on_rate_limit(lambda: client.search.accounts("surf"))
        assert results is not None


# ---------------------------------------------------------------------------
# Custom Feeds
# ---------------------------------------------------------------------------

class TestCustomFeeds:
    feed_id = None

    def test_01_create(self, client):
        feed = retry_on_rate_limit(lambda: client.custom_feeds.create(
            title=f"SDK Test {int(time.time())}",
            description="Python SDK integration test -- safe to delete",
        ))
        assert feed is not None
        raw_id = feed.get("id") or feed.get("surfId") or ""
        TestCustomFeeds.feed_id = raw_id.replace("surf/custom/", "")
        assert TestCustomFeeds.feed_id

    def test_02_add_operators(self, client):
        if not self.feed_id:
            pytest.skip("No feed created")
        operators = [
            {"surfId": "surf/topic/technology", "operator": "source"},
            {"surfId": "surf/hashtag/opensource", "operator": "source"},
            {"surfId": "bluesky/user/@jay.bsky.team", "operator": "source"},
        ]
        for op in operators:
            retry_on_rate_limit(lambda op=op: client.custom_feeds.add_operator(self.feed_id, op))

    def test_03_get_and_verify(self, client):
        if not self.feed_id:
            pytest.skip("No feed created")
        feed = retry_on_rate_limit(lambda: client.custom_feeds.get(self.feed_id))
        assert feed is not None
        ops = feed.get("operators", [])
        stored = {op.get("surfId") for op in ops}
        assert "surf/topic/technology" in stored
        assert "surf/hashtag/opensource" in stored

    def test_04_list(self, client):
        feeds = retry_on_rate_limit(lambda: client.custom_feeds.list())
        assert isinstance(feeds, list)

    def test_05_delete(self, client):
        if not self.feed_id:
            pytest.skip("No feed created")
        try:
            retry_on_rate_limit(lambda: client.custom_feeds.delete(self.feed_id))
        except SurfNotFoundError:
            pass  # already deleted by a previous test run


# ---------------------------------------------------------------------------
# Write Ops -- Mastodon
# ---------------------------------------------------------------------------

class TestWriteMastodon:
    post_id = None

    def test_01_create_post(self, client):
        result = retry_on_rate_limit(lambda: client.feeds.create_post(
            f"Python SDK test {int(time.time())} -- safe to delete",
            service="mastodon",
        ))
        assert result is not None
        TestWriteMastodon.post_id = result.get("id")
        assert TestWriteMastodon.post_id

    def test_02_favourite(self, client):
        if not self.post_id:
            pytest.skip("No post created")
        retry_on_rate_limit(lambda: client.feeds.favourite(self.post_id, service="mastodon"))

    def test_03_unfavourite(self, client):
        if not self.post_id:
            pytest.skip("No post created")
        retry_on_rate_limit(lambda: client.feeds.unfavourite(self.post_id, service="mastodon"))

    def test_04_bookmark(self, client):
        if not self.post_id:
            pytest.skip("No post created")
        retry_on_rate_limit(lambda: client.feeds.bookmark(self.post_id, service="mastodon"))

    def test_05_delete(self, client):
        if not self.post_id:
            pytest.skip("No post created")
        retry_on_rate_limit(lambda: client.feeds.delete_post(self.post_id, service="mastodon"))


# ---------------------------------------------------------------------------
# Write Ops -- Bluesky
# ---------------------------------------------------------------------------

class TestWriteBluesky:
    post_id = None

    def test_01_create_post(self, client):
        result = retry_on_rate_limit(lambda: client.feeds.create_post(
            f"Python SDK test {int(time.time())} -- safe to delete",
            service="bluesky",
        ))
        assert result is not None
        TestWriteBluesky.post_id = result.get("id")
        assert TestWriteBluesky.post_id

    def test_02_favourite(self, client):
        if not self.post_id:
            pytest.skip("No post created")
        retry_on_rate_limit(lambda: client.feeds.favourite(self.post_id, service="bluesky"))

    def test_03_delete(self, client):
        if not self.post_id:
            pytest.skip("No post created")
        retry_on_rate_limit(lambda: client.feeds.delete_post(self.post_id, service="bluesky"))


# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------

class TestAI:
    def test_feed_summary(self, client):
        result = retry_on_rate_limit(lambda: client.ai.feed_summary("surf/topic/technology"))
        assert result is not None

    def test_ask(self, client):
        try:
            result = retry_on_rate_limit(lambda: client.ai.ask("feeds about renewable energy"))
            assert result is not None
        except SurfAPIError:
            pytest.skip("NLWeb service unavailable")


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------

class TestErrors:
    def test_invalid_token(self):
        import os
        base_url = os.environ.get("SURF_API_BASE_URL", "")
        if base_url:
            base_url = base_url.rstrip("/").removesuffix("/v1")
            bad = SurfClient("invalid_token_xxx", base_url=base_url)
        else:
            bad = SurfClient("invalid_token_xxx")
        with pytest.raises(SurfAuthError):
            bad.feeds.get("surf/topic/technology")

    def test_not_found(self, client):
        # Use a completely invalid surf ID format that returns 404
        with pytest.raises((SurfNotFoundError, SurfAPIError)):
            client.feeds.get("surf/nonexistent_type/12345")

    def test_rate_limit_info(self, client):
        client.feeds.get("surf/topic/technology")
        rl = client.rate_limit
        assert rl is not None
        assert rl.limit > 0
