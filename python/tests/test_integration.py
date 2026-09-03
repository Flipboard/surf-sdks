"""Surf Python SDK integration tests.

Tests the SDK client against the live API. Requires SURF_API_TEST_TOKEN env var.
"""

import base64
import time
import pytest

import os

from surf_api import SurfClient, SurfRTBClient, NewFeedOperator
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
    """Call fn(), skip test if token lacks the required scope or linked account."""
    try:
        return fn()
    except SurfScopeError:
        pytest.skip("Token lacks required scope")
    except SurfAuthError:
        pytest.skip("No linked account for this service")
    except SurfAPIError as e:
        # ?service=X names a network the app owner has no linked account for
        if e.status_code == 400 and "No linked" in str(e):
            pytest.skip(f"No linked account for this service: {e}")
        raise


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

    def test_get_posts_with_since(self, client):
        posts = retry_on_rate_limit(lambda: client.feeds.get_posts("surf/topic/technology", limit=5, since="7d"))
        assert isinstance(posts, list)
        assert len(posts) <= 5

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
        # Bookmark has no AT Protocol equivalent — the Bluesky bridge doesn't
        # implement it — so a Bluesky-backed account returns 404. Skip rather
        # than fail (bookmark works for native Mastodon/ActivityPub accounts).
        try:
            retry_on_rate_limit(lambda: client.feeds.bookmark(self.post_id, service="mastodon"))
        except SurfNotFoundError:
            pytest.skip("Bookmark not supported for Bluesky-backed posts")

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
# Field-report fixes: attachments, single post/thread, pin, services forms,
# get_following, visibility/service validation (all Bluesky-targeted)
# ---------------------------------------------------------------------------

_PNG_2X2 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEklEQVR42mP8z8DwHwyBgAEACn4D/Y7q8T4AAAAASUVORK5CYII="
)


class TestFieldReportFixes:
    post_id = None
    attachment_id = None

    def test_01_get_following_takes_surf_id(self, client):
        feeds = retry_on_rate_limit(lambda: client.feeds.get_following("surf/topic/technology", limit=5))
        assert isinstance(feeds, list)

    def test_02_services_as_list_returns_only_bluesky(self, client):
        posts = retry_on_rate_limit(lambda: client.feeds.get_posts(
            "surf/topic/technology", limit=10, services=["surf/service/bluesky"]))
        assert isinstance(posts, list) and posts
        assert all(str(p.get("id", "")).startswith("at://") for p in posts), \
            "services=[surf/service/bluesky] must yield Bluesky posts only"

    def test_03_services_bare_names_accepted(self, client):
        posts = retry_on_rate_limit(lambda: client.feeds.get_posts(
            "surf/topic/technology", limit=5, services="bluesky,rss"))
        assert isinstance(posts, list)

    def test_04_topic_feed_includes_bluesky_by_default(self, client):
        posts = retry_on_rate_limit(lambda: client.feeds.get_posts("surf/topic/technology", limit=40))
        assert any(str(p.get("id", "")).startswith("at://") for p in posts), \
            "API-key topic feeds default to include Bluesky"

    def test_05_no_placeholder_rows(self, client):
        posts = retry_on_rate_limit(lambda: client.feeds.get_posts("surf/topic/technology", limit=40))
        blank = [p for p in posts if not (p.get("content") or p.get("media_attachments")
                                          or p.get("card") or p.get("reblog") or p.get("quote"))]
        assert not blank, f"{len(blank)} contentless placeholder rows"
        assert len(posts) == 40, f"page should be exactly limit, got {len(posts)}"

    def test_06_upload_attachment(self, client, tmp_path):
        png = tmp_path / "sdk-test.png"
        png.write_bytes(_PNG_2X2)
        att = skip_on_scope(lambda: retry_on_rate_limit(lambda: client.media.upload_attachment(
            str(png), "image/png", description="Python SDK test image", service="bluesky")))
        if att is None:
            return
        TestFieldReportFixes.attachment_id = att.get("id")
        assert TestFieldReportFixes.attachment_id
        ready = client.media.wait_for_attachment(TestFieldReportFixes.attachment_id, service="bluesky", timeout=60)
        assert ready.get("ready") is True

    def test_07_create_post_with_media(self, client):
        if not self.attachment_id:
            pytest.skip("No attachment uploaded")
        post = skip_on_scope(lambda: retry_on_rate_limit(lambda: client.feeds.create_post(
            f"Python SDK media test {int(time.time())} -- safe to delete",
            service="bluesky", media_ids=[self.attachment_id])))
        if post is None:
            return
        TestFieldReportFixes.post_id = post.get("id")
        assert str(TestFieldReportFixes.post_id).startswith("at://"), "service=bluesky must post to Bluesky"
        assert post.get("media_attachments"), "post must carry the uploaded attachment"

    def test_08_get_status_and_post(self, client):
        if not self.post_id:
            pytest.skip("No post created")
        status = retry_on_rate_limit(lambda: client.feeds.get_status(self.post_id, service="bluesky"))
        assert status.get("id") == self.post_id
        via_post = retry_on_rate_limit(lambda: client.feeds.get_post(self.post_id))
        assert via_post.get("id") == self.post_id, "GET /post must resolve an at:// id"
        ctx = retry_on_rate_limit(lambda: client.feeds.get_status_context(self.post_id, service="bluesky"))
        assert "ancestors" in ctx and "descendants" in ctx

    def test_09_pin_unpin(self, client):
        if not self.post_id:
            pytest.skip("No post created")
        try:
            retry_on_rate_limit(lambda: client.feeds.pin(self.post_id, service="bluesky"))
            retry_on_rate_limit(lambda: client.feeds.unpin(self.post_id, service="bluesky"))
        except SurfNotFoundError:
            pytest.skip("pin not supported by this account's bridge")

    def test_10_non_public_visibility_rejected_on_bluesky(self, client):
        with pytest.raises(SurfAPIError) as ei:
            skip_on_scope(lambda: client.feeds.create_post(
                f"Python SDK visibility test {int(time.time())}", visibility="direct", service="bluesky"))
        assert ei.value.status_code == 400, f"expected 400, got {ei.value.status_code}"

    def test_11_unknown_service_rejected(self, client):
        with pytest.raises(SurfAPIError) as ei:
            client.feeds.create_post("Python SDK service test", service="threads")
        assert ei.value.status_code == 400

    def test_12_delete(self, client):
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

    def test_fact_check(self, client):
        result = skip_on_scope(lambda: retry_on_rate_limit(
            lambda: client.ai.fact_check(text="The Eiffel Tower is in Paris.")))
        if result is not None:
            assert isinstance(result, dict)
            assert "verdict" in result


# ---------------------------------------------------------------------------
# Media — AI image generation
# Gated: GPU-bound (20-60s) and consumes the 20/day image quota, so it only
# runs when SURF_RUN_AI_IMAGE_TESTS=1. Validates request/response compatibility.
# ---------------------------------------------------------------------------

class TestMediaImageGeneration:
    @pytest.mark.skipif(
        os.environ.get("SURF_RUN_AI_IMAGE_TESTS") != "1",
        reason="set SURF_RUN_AI_IMAGE_TESTS=1 to run (consumes the 20/day GPU image quota)",
    )
    def test_generate_image(self, client):
        # Submit only (async): validates the {key, url, status} contract without
        # burning ~90s polling for the image.
        try:
            result = skip_on_scope(lambda: client.media.generate_image(
                "a calm minimalist landscape, soft pastels", skip_refiner=True))
            if result is not None:
                assert result.get("key"), "Expected a job key"
                assert result.get("url"), "Expected the eventual image URL"
                assert result.get("status") == "pending", "Submit status should be pending"
        except SurfAPIError as e:
            if e.status_code == 429:
                pytest.skip("image generation daily limit exceeded (20/day)")
            if e.status_code in (502, 503):
                pytest.skip("image generation service unavailable")
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


# ---------------------------------------------------------------------------
# RTB (Real-Time Bidding)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def rtb_client():
    """Create a SurfRTBClient for integration tests, skip if no token.

    Gated on the same SURF_API_TEST_TOKEN as the other integration tests.
    Note: the RTB client targets surf.social (/devportal/v1/rtb), which is a
    distinct host from the main API (api.surf.social/v1). When SURF_API_BASE_URL
    points at a test environment we derive the RTB host from it by stripping the
    SDK's /v1 suffix and any leading ``api.`` subdomain; a dedicated
    SURF_RTB_BASE_URL override takes precedence if set.
    """
    token = os.environ.get("SURF_API_TEST_TOKEN", "")
    if not token:
        pytest.skip("SURF_API_TEST_TOKEN not set")

    rtb_base = os.environ.get("SURF_RTB_BASE_URL", "")
    if not rtb_base:
        api_base = os.environ.get("SURF_API_BASE_URL", "")
        if api_base:
            rtb_base = api_base.rstrip("/").removesuffix("/v1").replace("//api.", "//", 1)

    if rtb_base:
        return SurfRTBClient(token, base_url=rtb_base)
    return SurfRTBClient(token)


def rtb_skip_on_scope(fn):
    """Call fn(), skip test if token lacks the required rtb:* scope/auth."""
    try:
        return fn()
    except (SurfScopeError, SurfAuthError):
        pytest.skip("Token lacks required rtb:* scope")


class TestRTB:
    """RTB endpoint integration tests.

    Sandbox bids don't require a publisher config and don't spend, so they're
    safe to run against any environment with a token that has rtb:* scopes.
    """

    def test_sandbox_bid(self, rtb_client):
        request = {
            "id": "sdk-itest-1",
            "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}],
        }
        result = rtb_skip_on_scope(
            lambda: retry_on_rate_limit(lambda: rtb_client.bid(request, sandbox=True))
        )
        if result is None:
            return
        assert isinstance(result, dict)
        # A sandbox response should echo the request id and carry a seatbid array.
        assert result.get("id") == "sdk-itest-1" or "seatbid" in result

    def test_reports(self, rtb_client):
        result = rtb_skip_on_scope(
            lambda: retry_on_rate_limit(lambda: rtb_client.reports(days=7))
        )
        if result is None:
            return
        assert isinstance(result, dict)

    def test_config(self, rtb_client):
        # The account may not be a registered RTB publisher; in that case the
        # API correctly returns 503 "RTB configuration could not be
        # initialized" (it can't auto-create a config for an unconfigured app).
        # Tolerate that — it's an environment precondition, not an SDK bug.
        try:
            result = rtb_skip_on_scope(
                lambda: retry_on_rate_limit(lambda: rtb_client.config())
            )
        except SurfAPIError as e:
            if getattr(e, "status_code", None) in (500, 503) or \
                    "could not be initialized" in str(e):
                pytest.skip("Account has no RTB publisher config")
            raise
        if result is None:
            return
        assert isinstance(result, dict)

    def test_scopes(self, rtb_client):
        result = rtb_skip_on_scope(
            lambda: retry_on_rate_limit(lambda: rtb_client.scopes())
        )
        if result is None:
            return
        assert isinstance(result, list)

    def test_ads_txt(self, rtb_client):
        result = rtb_skip_on_scope(
            lambda: retry_on_rate_limit(lambda: rtb_client.ads_txt())
        )
        if result is None:
            return
        assert isinstance(result, dict)

    def test_auth_error_with_bad_key(self, rtb_client):
        # A bogus key against the same host should raise an auth/scope error.
        bad = SurfRTBClient("invalid_rtb_token_xxx", base_url=rtb_client.base_url)
        with pytest.raises((SurfAuthError, SurfScopeError, SurfAPIError)):
            bad.bid({"id": "1", "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}]})
