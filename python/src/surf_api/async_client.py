"""Async Surf API client using httpx.

Usage::

    import asyncio
    from surf_api.async_client import AsyncSurfClient

    async def main():
        async with AsyncSurfClient("surf_sk_live_...") as client:
            feed = await client.feeds.get("surf/topic/technology")
            posts = await client.feeds.get_posts("surf/topic/technology")
            summary = await client.ai.feed_summary("surf/topic/technology")

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Optional

try:
    import httpx
except ImportError:
    raise ImportError(
        "httpx is required for the async client. Install with: pip install surf-api[async]"
    )

from .exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
    SurfScopeError,
)

DEFAULT_BASE_URL = "https://api.surf.social"
# Internal path prefix — the SDK handles this automatically.
API_PREFIX = "/v1"


class RateLimitInfo:
    """Rate limit information from response headers."""

    def __init__(self, headers):
        self.limit = int(headers.get("x-ratelimit-limit", 0))
        self.remaining = int(headers.get("x-ratelimit-remaining", 0))
        self.reset = headers.get("x-ratelimit-reset")

    def __repr__(self):
        return f"RateLimitInfo(remaining={self.remaining}/{self.limit}, reset={self.reset})"


class AsyncSurfClient:
    """Async client for the Surf API (uses httpx).

    Use as an async context manager for proper connection cleanup::

        async with AsyncSurfClient("surf_sk_live_...") as client:
            feed = await client.feeds.get("surf/topic/technology")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit: Optional[RateLimitInfo] = None

        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}{API_PREFIX}",
            headers={
                "X-API-Key": api_key,
                "Accept": "application/json",
                "User-Agent": "surf-api-python-async/1.0.0",
            },
            timeout=timeout,
        )

        # Sub-clients
        self.feeds = _AsyncFeedsAPI(self)
        self.search = _AsyncSearchAPI(self)
        self.ai = _AsyncAIAPI(self)
        self.account = _AsyncAccountAPI(self)
        self.content = _AsyncContentAPI(self)
        self.images = _AsyncImagesAPI(self)
        self.audio = _AsyncAudioAPI(self)
        self.notifications = _AsyncNotificationsAPI(self)
        self.preferences = _AsyncPreferencesAPI(self)
        self.custom_feeds = _AsyncCustomFeedsAPI(self)
        self.media = _AsyncMediaAPI(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        """Close the underlying httpx client."""
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                self.rate_limit = RateLimitInfo(resp.headers)

                if resp.status_code == 429 and attempt < self.max_retries:
                    retry_after = int(resp.headers.get("retry-after", 2 ** attempt))
                    await asyncio.sleep(min(retry_after, 60))
                    continue
                if resp.status_code >= 500 and attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue

                self._check_errors(resp)
                if resp.status_code == 204:
                    return {}
                return resp.json()
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exc = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise SurfAPIError(
                    f"Connection failed after {self.max_retries + 1} attempts: {e}",
                    status_code=0,
                    error_code="connection_error",
                )
        if last_exc:
            raise last_exc
        return {}

    async def _request_raw(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make a request and return the raw httpx.Response."""
        resp = await self._client.request(method, path, **kwargs)
        self.rate_limit = RateLimitInfo(resp.headers)
        self._check_errors(resp)
        return resp

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        return await self._request("GET", path, params=_clean(params))

    async def _post(self, path: str, json: Optional[dict] = None, **kwargs) -> dict:
        return await self._request("POST", path, json=json, **kwargs)

    async def _put(self, path: str, json: Optional[dict] = None) -> dict:
        return await self._request("PUT", path, json=json)

    async def _patch(self, path: str, json: Optional[dict] = None) -> dict:
        return await self._request("PATCH", path, json=json)

    async def _delete(self, path: str) -> dict:
        return await self._request("DELETE", path)

    def _check_errors(self, resp: httpx.Response):
        if resp.is_success:
            return
        try:
            body = resp.json()
        except Exception:
            body = {}
        msg = body.get("error_description") or body.get("error") or resp.text
        kwargs = dict(
            status_code=resp.status_code,
            error_code=body.get("error"),
        )
        if resp.status_code == 401:
            raise SurfAuthError(msg, **kwargs)
        if resp.status_code == 403:
            raise SurfScopeError(msg, **kwargs)
        if resp.status_code == 404:
            raise SurfNotFoundError(msg, **kwargs)
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            raise SurfRateLimitError(msg, retry_after=retry_after, **kwargs)
        raise SurfAPIError(msg, **kwargs)

    async def paginate(self, path: str, key: str, params: Optional[dict] = None,
                       limit: Optional[int] = None) -> AsyncIterator[Any]:
        """Auto-paginate through results, yielding individual items.

        Args:
            path: API path (e.g. ``/feed/posts``)
            key: Response key whose value is the list of items (e.g. ``"posts"``)
            params: Base query parameters (copied; not mutated)
            limit: Maximum items to yield. ``None``, ``0``, or any negative
                value means no limit.
        """
        params = dict(params or {})
        fetched = 0
        while True:
            if limit is not None and limit > 0 and fetched >= limit:
                return
            data = await self._get(path, params)
            if not isinstance(data, dict):
                raise SurfAPIError(
                    f"paginate: expected a JSON object response from {path!r}, "
                    f"got {type(data).__name__}",
                    status_code=0, error_code="invalid_response",
                )
            if key not in data:
                break
            raw_items = data[key]
            if not isinstance(raw_items, list):
                raise SurfAPIError(
                    f"paginate: expected {key!r} to be a list, "
                    f"got {type(raw_items).__name__}",
                    status_code=0, error_code="invalid_response",
                )
            if not raw_items:
                break
            for item in raw_items:
                yield item
                fetched += 1
                if limit is not None and limit > 0 and fetched >= limit:
                    return
            cursor = data.get("cursor") or data.get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor


# ==========================================================================
# Feeds
# ==========================================================================

class _AsyncFeedsAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def get(self, surf_id: str) -> dict:
        return await self._c._get("/feed", {"surf_id": surf_id})

    async def get_posts(self, surf_id: str, limit: int = 20, cursor: str = None,
                        sort: str = None, services: str = None) -> dict:
        return await self._c._get("/feed/posts", {
            "surf_id": surf_id, "limit": limit, "cursor": cursor,
            "sort": sort, "services": services,
        })

    async def iter_posts(self, surf_id: str, limit: int = None, page_size: int = 40,
                         sort: str = None, services: str = None) -> AsyncIterator[dict]:
        """Auto-paginate through all posts. Yields individual post dicts."""
        cursor = None
        fetched = 0
        while True:
            data = await self.get_posts(surf_id, limit=page_size, cursor=cursor,
                                        sort=sort, services=services)
            posts = data if isinstance(data, list) else data.get("posts", []) if isinstance(data, dict) else []
            if not posts:
                break
            for post in posts:
                yield post
                fetched += 1
                if limit and fetched >= limit:
                    return
            cursor = data.get("cursor") if isinstance(data, dict) else None
            if not cursor:
                break

    async def get_post(self, post_id: str, thread: bool = False) -> dict:
        return await self._c._get("/post", {"id": post_id, "thread": str(thread).lower()})

    async def get_following(self, limit: int = 50) -> dict:
        return await self._c._get("/feed/following", {"limit": limit})

    async def get_speeddial(self) -> dict:
        return await self._c._get("/feed/speeddial")

    async def create_post(self, status: str, visibility: str = "public",
                          in_reply_to_id: str = None, service: str = None,
                          **kwargs) -> dict:
        body = {"status": status, "visibility": visibility, **kwargs}
        if in_reply_to_id:
            body["in_reply_to_id"] = in_reply_to_id
        path = "/statuses"
        if service:
            path += f"?service={service}"
        return await self._c._post(path, json=body)

    async def favourite(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{post_id}/favourite"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def unfavourite(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{post_id}/unfavourite"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def boost(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{post_id}/reblog"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def unboost(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{post_id}/unreblog"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def bookmark(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{post_id}/bookmark"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def unbookmark(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{post_id}/unbookmark"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def delete_post(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{post_id}"
        if service:
            path += f"?service={service}"
        return await self._c._delete(path)


# ==========================================================================
# Search
# ==========================================================================

class _AsyncSearchAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def search(self, query: str, type: str = "feeds", limit: int = 20) -> dict:
        return await self._c._get("/search", {"q": query, "type": type, "limit": limit})

    async def feeds(self, query: str, limit: int = 20) -> dict:
        return await self.search(query, type="feeds", limit=limit)

    async def posts(self, query: str, limit: int = 20) -> dict:
        return await self.search(query, type="posts", limit=limit)

    async def accounts(self, query: str, limit: int = 20) -> dict:
        return await self.search(query, type="accounts", limit=limit)

    async def podcasts(self, query: str, limit: int = 20) -> dict:
        return await self.search(query, type="podcasts", limit=limit)

    async def discover(self, type: str = "recommended", surf_id: str = None, limit: int = 20) -> dict:
        return await self._c._get("/search/discover", {
            "type": type, "surf_id": surf_id, "limit": limit,
        })


# ==========================================================================
# AI
# ==========================================================================

class _AsyncAIAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def ask(self, query: str, k: int = 10, schema_type: str = None, feed_id: str = None) -> dict:
        return await self._c._get("/ai/ask", {
            "query": query, "k": k, "schema_type": schema_type, "feed_id": feed_id,
        })

    async def feed_summary(self, surf_id: str, limit: int = 20) -> dict:
        return await self._c._get("/ai/feed-summary", {"surf_id": surf_id, "limit": limit})

    async def thread_summary(self, post_at: str) -> dict:
        return await self._c._get("/ai/thread-summary", {"post_at": post_at})

    async def build_feed(self, prompt: str, feed_id: str = None) -> AsyncIterator[str]:
        """Build a custom feed using AI (SSE stream)."""
        async with self._c._client.stream(
            "POST", "/ai/feed-builder",
            json={"prompt": prompt, "feed_id": feed_id},
            timeout=60.0,
        ) as resp:
            self._c._check_errors(resp)
            async for line in resp.aiter_lines():
                if line.strip():
                    yield line


# ==========================================================================
# Account
# ==========================================================================

class _AsyncAccountAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def get(self) -> dict:
        return await self._c._get("/account")

    async def update(self, **fields) -> dict:
        return await self._c._put("/account", json=fields)

    async def lookup(self, account: str) -> dict:
        return await self._c._get("/account/lookup", {"account": account})

    async def get_links(self) -> dict:
        return await self._c._get("/account/links")

    async def add_link(self, title: str, url: str, icon: str = None) -> dict:
        body = {"title": title, "url": url}
        if icon:
            body["icon"] = icon
        return await self._c._post("/account/links", json=body)

    async def update_link(self, link_id: str, **fields) -> dict:
        fields["id"] = link_id
        return await self._c._put(f"/account/links/{link_id}", json=fields)

    async def delete_link(self, link_id: str) -> dict:
        return await self._c._delete(f"/account/links/{link_id}")

    async def follow(self, account_id: str, service: str = None) -> dict:
        path = f"/accounts/{account_id}/follow"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def unfollow(self, account_id: str, service: str = None) -> dict:
        path = f"/accounts/{account_id}/unfollow"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def get_connected_apps(self) -> dict:
        return await self._c._get("/account/connected-apps")

    async def revoke_connected_app(self, authorization_id: int) -> dict:
        return await self._c._post(f"/account/connected-apps/{authorization_id}/revoke")


# ==========================================================================
# Content
# ==========================================================================

class _AsyncContentAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def resolve(self, url: str) -> dict:
        return await self._c._get("/content/resolve", {"url": url})

    async def extract(self, url: str, type: str = "article") -> dict:
        return await self._c._get("/content/extract", {"url": url, "type": type})

    async def language(self, url: str) -> dict:
        return await self._c._get("/content/language", {"url": url})

    async def topics(self, url: str) -> dict:
        return await self._c._get("/content/topics", {"url": url})

    async def enrich(self, post_id: str) -> dict:
        return await self._c._get("/content/enrich", {"post_id": post_id})


# ==========================================================================
# Images
# ==========================================================================

class _AsyncImagesAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def info(self, url: str) -> dict:
        return await self._c._get("/image/info", {"url": url})

    async def resize(self, url: str, size: str = "medium") -> bytes:
        resp = await self._c._request_raw("GET", "/image/resize", params={"url": url, "size": size})
        return resp.content

    async def colors(self, url: str, k: int = 5) -> bytes:
        resp = await self._c._request_raw("GET", "/image/colors", params={"url": url, "k": k})
        return resp.content

    async def moderate(self, url: str) -> dict:
        return await self._c._get("/image/moderate", {"url": url})


# ==========================================================================
# Audio
# ==========================================================================

class _AsyncAudioAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def list_stations(self) -> dict:
        return await self._c._get("/audio/radio/stations")

    async def get_station(self, station_id: str) -> dict:
        return await self._c._get(f"/audio/radio/stations/{station_id}")

    async def create_station(self, feed_surf_id: str, title: str = None) -> dict:
        body = {"feed_surf_id": feed_surf_id}
        if title:
            body["title"] = title
        return await self._c._post("/audio/radio/stations", json=body)

    async def generate_program(self, station_id: str) -> dict:
        return await self._c._post(f"/audio/radio/stations/{station_id}/generate")

    async def get_program(self, program_id: str) -> dict:
        return await self._c._get(f"/audio/radio/programs/{program_id}")

    async def generate_briefing(self) -> dict:
        return await self._c._post("/audio/briefing/generate")

    async def get_briefing(self, briefing_id: str = None) -> dict:
        if briefing_id:
            return await self._c._get(f"/audio/briefing/{briefing_id}")
        return await self._c._get("/audio/briefing/latest")

    async def get_transcript(self, episode_url: str) -> dict:
        return await self._c._get("/audio/transcript", {"episode_url": episode_url})

    async def get_daily_quiz(self) -> dict:
        return await self._c._get("/audio/quiz/daily")

    async def text_to_speech(self, text: str, voice: str = "en-US-AriaNeural") -> bytes:
        resp = await self._c._request_raw("POST", "/audio/tts", json={"text": text, "voice": voice})
        return resp.content


# ==========================================================================
# Notifications
# ==========================================================================

class _AsyncNotificationsAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def list(self, limit: int = 30, cursor: str = None, type: str = None) -> dict:
        return await self._c._get("/notifications", {"limit": limit, "cursor": cursor, "type": type})

    async def mark_read(self) -> dict:
        return await self._c._post("/notifications/read")


# ==========================================================================
# Preferences
# ==========================================================================

class _AsyncPreferencesAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def get(self) -> dict:
        return await self._c._get("/preferences/account")

    async def update(self, **preferences) -> dict:
        return await self._c._patch("/preferences/account", json=preferences)


# ==========================================================================
# Custom Feeds
# ==========================================================================

class _AsyncCustomFeedsAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def list(self) -> dict:
        return await self._c._get("/custom")

    async def get(self, feed_id: str) -> dict:
        return await self._c._get(f"/custom/{feed_id}")

    async def create(self, title: str, description: str = None, operators: list = None) -> dict:
        body = {"title": title}
        if description:
            body["description"] = description
        if operators:
            body["operators"] = operators
        return await self._c._post("/custom", json=body)

    async def update(self, feed_id: str, **kwargs) -> dict:
        return await self._c._put(f"/custom/{feed_id}", json=kwargs)

    async def delete(self, feed_id: str) -> dict:
        return await self._c._delete(f"/custom/{feed_id}")

    async def clone(self, feed_id: str) -> dict:
        return await self._c._post(f"/custom/{feed_id}/clone")

    async def publish(self, feed_id: str) -> dict:
        return await self._c._post(f"/custom/{feed_id}/publish")

    async def unpublish(self, feed_id: str) -> dict:
        return await self._c._post(f"/custom/{feed_id}/unpublish")

    async def add_operator(self, feed_id: str, operator: dict) -> dict:
        return await self._c._post(f"/custom/{feed_id}/operators", json=[operator])

    async def add_operators(self, feed_id: str, operators: list) -> dict:
        return await self._c._post(f"/custom/{feed_id}/operators", json=operators)

    async def update_operator(self, feed_id: str, operator_id: str, operator: dict) -> dict:
        return await self._c._put(f"/custom/{feed_id}/operators/{operator_id}", json=operator)

    async def remove_operator(self, feed_id: str, operator_id: str) -> dict:
        return await self._c._delete(f"/custom/{feed_id}/operators/{operator_id}")


# ==========================================================================
# Media
# ==========================================================================

class _AsyncMediaAPI:
    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def upload(self, file_path: str, content_type: str = "image/jpeg") -> dict:
        """Upload a media file (image)."""
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f, content_type)}
            resp = await self._c._client.post("/media/upload", files=files)
        self._c.rate_limit = RateLimitInfo(resp.headers)
        self._c._check_errors(resp)
        return resp.json()


def _clean(params: Optional[dict]) -> Optional[dict]:
    """Remove None values from params dict."""
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
