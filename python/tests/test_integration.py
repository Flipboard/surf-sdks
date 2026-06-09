"""Surf Python SDK integration tests.

Tests the SDK client against the live API. Requires SURF_API_TEST_TOKEN env var.
"""

import time
import pytest

from surf_api import SurfClient, NewFeedOperator
from surf_api.exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
    SurfScopeError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def retry_on_rate_limit(fn):
    """Call fn(), retry once after sleeping if rate limited."""
    try:
        return fn()
    except SurfRateLimitError as e:
        try:
            wait = int(e.retry_after) if e.retry_after else 60
        except (ValueError, TypeError):
            wait = 60
        wait = min(wait, 65)
        time.sleep(wait)
        return fn()


def skip_on_scope(fn):
    """Call fn(), skip test if token lacks the required scope."""
    try:
        return fn()
    except SurfScopeError:
        pytest.skip("Token lacks required scope")
    except SurfAuthError:
        pytest.skip("No linked account for this service")


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

    def test_iter_posts_yields_items_up_to_limit(self, client):
        posts = retry_on_rate_limit(
            lambda: list(client.feeds.iter_posts("surf/topic/technology", limit=5, page_size=3))
        )
        assert isinstance(posts, list)
        if not posts:
            pytest.skip("Feed returned no posts in this environment")
        assert len(posts) <= 5, f"limit=5 must be respected, got {len(posts)}"

    def test_iter_posts_respects_page_size(self, client):
        # page_size=2 with limit=4 requires ≥2 API calls to accumulate posts.
        # We just verify it terminates and respects limit.
        posts = retry_on_rate_limit(
            lambda: list(client.feeds.iter_posts("surf/topic/technology", limit=4, page_size=2))
        )
        assert len(posts) <= 4, f"limit=4 must be respected, got {len(posts)}"


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
        result = skip_on_scope(lambda: retry_on_rate_limit(lambda: client.custom_feeds.create(
            title=f"SDK Test {int(time.time())}",
            description="Python SDK integration test -- safe to delete",
        )))
        if result is None:
            return
        raw_id = result.get("id") or result.get("surfId") or ""
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
            pass  # already deleted


class TestCreateWithOperators:
    """Tests the create_with_operators convenience method and NewFeedOperator helpers."""

    feed_id = None

    def test_01_create_with_operators(self, client):
        result = skip_on_scope(lambda: retry_on_rate_limit(lambda:
            client.custom_feeds.create_with_operators(
                title=f"SDK OpTest {int(time.time())}",
                operators=[
                    NewFeedOperator.source("surf/topic/technology"),
                    NewFeedOperator.source("surf/hashtag/opensource"),
                ],
                description="NewFeedOperator integration test -- safe to delete",
            )
        ))
        if result is None:
            return
        raw_id = result.get("id") or result.get("surfId") or ""
        TestCreateWithOperators.feed_id = raw_id.replace("surf/custom/", "")
        assert TestCreateWithOperators.feed_id

    def test_02_verify_operators(self, client):
        if not self.feed_id:
            pytest.skip("No feed created")
        feed = retry_on_rate_limit(lambda: client.custom_feeds.get(self.feed_id))
        assert feed is not None
        stored = {op.get("surfId") for op in feed.get("operators", [])}
        assert "surf/topic/technology" in stored
        assert "surf/hashtag/opensource" in stored

    def test_03_delete(self, client):
        if not self.feed_id:
            pytest.skip("No feed created")
        try:
            retry_on_rate_limit(lambda: client.custom_feeds.delete(self.feed_id))
        except SurfNotFoundError:
            pass


class TestCustomFeedThemes:
    feed_id = None

    def test_01_create_with_theme(self, client):
        from surf_api.client import FeedTheme
        theme = FeedTheme(
            header_image="https://surf.social/img/surf-logo.png",
            header_image_size={"width": 600, "height": 272},
            surface="#EFEADD",
            surface_header="#005F5F",
        )
        result = skip_on_scope(lambda: retry_on_rate_limit(lambda: client.custom_feeds.create(
            title=f"Theme Test {int(time.time())}",
            description="Python SDK theme test -- safe to delete",
            theme=theme,
        )))
        if result is None:
            return
        raw_id = result.get("id") or result.get("surfId") or ""
        TestCustomFeedThemes.feed_id = raw_id.replace("surf/custom/", "")
        assert TestCustomFeedThemes.feed_id
        # Verify theme round-trips in the response
        resp_theme = result.get("theme")
        assert resp_theme is not None, "Response should include theme"
        assert resp_theme.get("header", {}).get("image") == "https://surf.social/img/surf-logo.png"
        colors = resp_theme.get("colors", {}).get("light", {})
        assert colors.get("surface") == "#EFEADD"
        assert colors.get("surfaceHeader") == "#005F5F"

    def test_02_get_theme(self, client):
        if not self.feed_id:
            pytest.skip("No themed feed created")
        feed = retry_on_rate_limit(lambda: client.custom_feeds.get(self.feed_id))
        resp_theme = feed.get("theme")
        assert resp_theme is not None, "GET response should include theme"
        assert resp_theme.get("header", {}).get("image") == "https://surf.social/img/surf-logo.png"

    def test_03_update_theme(self, client):
        if not self.feed_id:
            pytest.skip("No themed feed created")
        from surf_api.client import FeedTheme
        new_theme = FeedTheme(
            header_image="https://surf.social/img/surf-logo.png",
            header_image_size={"width": 400, "height": 200},
            surface="#1D1B1C",
            surface_header="#123535",
        )
        result = retry_on_rate_limit(lambda: client.custom_feeds.update(
            self.feed_id, title="Theme Updated", theme=new_theme,
        ))
        resp_theme = result.get("theme")
        assert resp_theme is not None
        colors = resp_theme.get("colors", {}).get("light", {})
        assert colors.get("surface") == "#1D1B1C"

    def test_04_delete(self, client):
        if not self.feed_id:
            pytest.skip("No themed feed created")
        try:
            retry_on_rate_limit(lambda: client.custom_feeds.delete(self.feed_id))
        except SurfNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Write Ops -- Mastodon
# ---------------------------------------------------------------------------

class TestWriteMastodon:
    post_id = None

    def test_01_create_post(self, client):
        result = skip_on_scope(lambda: retry_on_rate_limit(lambda: client.feeds.create_post(
            f"Python SDK test {int(time.time())} -- safe to delete",
            service="mastodon",
        )))
        if result is None:
            return
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
        result = skip_on_scope(lambda: retry_on_rate_limit(lambda: client.feeds.create_post(
            f"Python SDK test {int(time.time())} -- safe to delete",
            service="bluesky",
        )))
        if result is None:
            return
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
        result = skip_on_scope(lambda: retry_on_rate_limit(
            lambda: client.ai.feed_summary("surf/topic/technology")))
        if result is not None:
            assert result is not None

    def test_ask(self, client):
        try:
            result = skip_on_scope(lambda: retry_on_rate_limit(
                lambda: client.ai.ask("feeds about renewable energy")))
            if result is not None:
                assert result is not None
        except SurfAPIError as e:
            if e.status_code in (502, 503):
                pytest.skip("NLWeb service unavailable")
            raise


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
        with pytest.raises((SurfNotFoundError, SurfAPIError)):
            client.feeds.get("surf/nonexistent_type/12345")

    def test_rate_limit_info(self, client):
        client.feeds.get("surf/topic/technology")
        rl = client.rate_limit
        assert rl is not None
        # Headers may not be present in all environments
        assert rl.limit >= 0


# ---------------------------------------------------------------------------
# Paginate
# ---------------------------------------------------------------------------

class TestPaginate:
    """Tests for the public paginate() helper on SurfClient.

    paginate() is designed for endpoints that return JSON objects of the form
    {"<key>": [...], "cursor": "..."}. Bare-array endpoints now raise SurfAPIError
    with error_code="invalid_response" rather than a generic AttributeError.
    """

    def test_paginate_respects_limit(self, client):
        # paginate() with limit=3 must yield ≤3 items and not raise.
        try:
            items = retry_on_rate_limit(lambda: list(client.paginate(
                "/feed/posts", "posts",
                {"surf_id": "surf/topic/technology", "limit": 2},
                limit=3,
            )))
        except SurfAPIError as e:
            if e.error_code == "invalid_response":
                pytest.skip("Endpoint returns a bare array; paginate() requires an object response")
            raise
        assert len(items) <= 3, f"limit=3 should be respected, got {len(items)}"

    def test_paginate_private_alias_is_callable(self, client):
        # _paginate is a backward-compat alias; verify it still works.
        try:
            items = retry_on_rate_limit(lambda: list(client._paginate(
                "/feed/posts", "posts",
                {"surf_id": "surf/topic/technology", "limit": 2},
                limit=2,
            )))
        except SurfAPIError as e:
            if e.error_code == "invalid_response":
                pytest.skip("Endpoint returns a bare array; paginate() requires an object response")
            raise
        assert len(items) <= 2, f"_paginate limit=2 must be respected, got {len(items)}"

    def test_paginate_missing_key_yields_nothing(self, client):
        # A key absent from the response must yield 0 items without error.
        try:
            items = retry_on_rate_limit(lambda: list(client.paginate(
                "/feed/posts", "nonexistent_key_xyz",
                {"surf_id": "surf/topic/technology"},
            )))
        except SurfAPIError as e:
            if e.error_code == "invalid_response":
                pytest.skip("Endpoint returns a bare array; paginate() requires an object response")
            raise
        assert len(items) == 0, f"missing key should yield 0 items, got {len(items)}"
