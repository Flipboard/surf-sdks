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
from urllib.parse import quote

try:
    import httpx
except ImportError:
    raise ImportError(
        "httpx is required for the async client. Install with: pip install surf-api[async]"
    )

from .client import episode_url_sha1
from .exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
    SurfScopeError,
)

DEFAULT_BASE_URL = "https://api.surf.social"
# Developer-portal endpoints (diagnostics, debug bundles) live on a different
# host/prefix than the v1 data API. Overridable for non-prod backends.
DEFAULT_DEVPORTAL_URL = "https://surf.social/devportal/v1"
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
        devportal_url: str = DEFAULT_DEVPORTAL_URL,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.devportal_url = (devportal_url or DEFAULT_DEVPORTAL_URL).rstrip("/")
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
        self.longform = _AsyncLongformAPI(self)
        self.diagnostics = _AsyncDiagnosticsAPI(self)

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
                # Only update from responses that carry rate-limit headers —
                # devportal (diagnostics) responses omit them and would otherwise
                # clobber the last real data-API rate_limit with zeros.
                if "X-RateLimit-Limit" in resp.headers:
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

    # Developer-portal helpers (diagnostics, debug bundles) — absolute URLs
    # override the client's base_url in httpx.
    async def _dp_get(self, path: str, params: Optional[dict] = None) -> dict:
        return await self._request("GET", f"{self.devportal_url}{path}", params=_clean(params))

    async def _dp_post(self, path: str, json: Optional[dict] = None) -> dict:
        return await self._request("POST", f"{self.devportal_url}{path}", json=json)

    async def _dp_delete(self, path: str) -> dict:
        return await self._request("DELETE", f"{self.devportal_url}{path}")

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
                        sort: str = None, services: str = None, since: str = None) -> dict:
        """Get posts from a feed.

        `since`: recency cutoff for a digest — a rolling duration ('24h', '7d', '30m', '90s',
        or a bare number of seconds) or an absolute ISO 8601 timestamp; only posts created at
        or after the cutoff are returned.
        """
        return await self._c._get("/feed/posts", {
            "surf_id": surf_id, "limit": limit, "cursor": cursor,
            "sort": sort, "services": services, "since": since,
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
        path = f"/statuses/{quote(post_id, safe='')}/favourite"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def unfavourite(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{quote(post_id, safe='')}/unfavourite"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def boost(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{quote(post_id, safe='')}/reblog"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def unboost(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{quote(post_id, safe='')}/unreblog"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def bookmark(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{quote(post_id, safe='')}/bookmark"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def unbookmark(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{quote(post_id, safe='')}/unbookmark"
        if service:
            path += f"?service={service}"
        return await self._c._post(path)

    async def delete_post(self, post_id: str, service: str = None) -> dict:
        path = f"/statuses/{quote(post_id, safe='')}"
        if service:
            path += f"?service={service}"
        return await self._c._delete(path)


# ==========================================================================
# Search
# ==========================================================================

class _AsyncSearchAPI:
    _PATHS = {
        "posts": "/search/posts",
        "feeds": "/search/maestra/feeds",
        "accounts": "/search/bluesky/searchActors",
        "podcasts": "/search/maestra/feeds",
        "rss": "/search/rss/search",
    }

    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def search(self, query: str, type: str = "feeds", limit: int = 20, sort: str = None,
                     since: str = None, automated: bool = None, safety: str = None,
                     exclude_replies: bool = None) -> dict:
        path = self._PATHS.get(type)
        if path is None:
            raise ValueError(f"unsupported search type: {type!r}")
        params = {"q": query, "limit": limit}
        if type == "posts":
            if sort:
                params["sort"] = sort
            if since:
                params["since"] = since
            if automated is not None:
                params["automated"] = "true" if automated else "false"
            if safety:
                params["safety"] = safety
            if exclude_replies is not None:
                params["exclude_replies"] = "true" if exclude_replies else "false"
        return await self._c._get(path, params)

    async def feeds(self, query: str, limit: int = 20) -> dict:
        return await self.search(query, type="feeds", limit=limit)

    async def posts(self, query: str, limit: int = 20, sort: str = None,
                    since: str = None, automated: bool = None, safety: str = None,
                    exclude_replies: bool = None) -> dict:
        """Search for posts. `query` supports exact phrases in double quotes
        ('"climate change"') and boolean operators AND/&& and OR/|| between terms
        ('cats AND dogs'); the word forms are uppercase-only, plain keywords are
        implicit AND. Options as in the sync client."""
        return await self.search(query, type="posts", limit=limit, sort=sort,
                                 since=since, automated=automated, safety=safety,
                                 exclude_replies=exclude_replies)

    async def accounts(self, query: str, limit: int = 20) -> dict:
        return await self.search(query, type="accounts", limit=limit)

    async def podcasts(self, query: str, limit: int = 20) -> dict:
        return await self.search(query, type="podcasts", limit=limit)

    async def publications(self, q: str, count: int = 20, offset: int = 0) -> list:
        """Search for longform publications. ``offset`` maps to the API's ``from`` param."""
        return await self._c._get("/search/publications", {"q": q, "count": count, "from": offset})

    async def discover(self, type: str = "recommended", surf_id: str = None, limit: int = 20) -> dict:
        return await self._c._get("/search/discover", {
            "type": type, "surf_id": surf_id, "limit": limit,
        })


# ==========================================================================
# Longform (standard.site / Leaflet documents & publications)
# ==========================================================================

class _AsyncLongformAPI:
    """Longform documents & publications — standard.site / Leaflet.

    Mirrors :class:`surf_api.client._LongformAPI`. Pass raw AT-URIs — the SDK
    percent-encodes them into the path automatically.
    """

    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def document(self, uri: str, format: str = None) -> dict:
        """Get a longform document by AT-URI. format: 'html' (default) or 'blocks'."""
        return await self._c._get(f"/documents/{quote(uri, safe='')}", {"format": format})

    async def publication(self, uri: str) -> dict:
        """Get a publication by AT-URI."""
        return await self._c._get(f"/publications/{quote(uri, safe='')}")

    async def publication_documents(self, uri: str, tags: Optional[list] = None,
                                    count: int = 20, offset: int = 0) -> list:
        """List a publication's documents. ``offset`` maps to the API's ``from`` param."""
        return await self._c._get(f"/publications/{quote(uri, safe='')}/documents", {
            "tags": tags, "count": count, "from": offset,
        })

    async def search_publications(self, q: str, count: int = 20, offset: int = 0) -> list:
        """Search for publications (read:search scope). ``offset`` maps to ``from``."""
        return await self._c._get("/search/publications", {"q": q, "count": count, "from": offset})


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

    async def fact_check(self, text: str = None, post_surf_id: str = None,
                         feed_id: str = None) -> dict:
        """Fact-check a claim, paragraph, or post.

        Provide exactly one of ``text`` or ``post_surf_id``; raises
        ``ValueError`` if neither or both are given.
        """
        if bool(text) == bool(post_surf_id):
            raise ValueError("provide exactly one of 'text' or 'post_surf_id'")
        body = {}
        if text is not None:
            body["text"] = text
        if post_surf_id is not None:
            body["postSurfId"] = post_surf_id
        if feed_id is not None:
            body["feedId"] = feed_id
        return await self._c._post("/ai/fact-check", json=body)

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

    async def get_show_notes(self, episode_url: str, language: str = None) -> dict:
        """Structured, AI-generated show notes for a transcribed episode.
        Raises SurfNotFoundError if notes have not been generated yet."""
        return await self._c._get("/audio/transcripts/show-notes",
                                  {"episode_url": episode_url, "language": language})

    # Podcast intelligence
    async def search_podcast_episodes(self, query: str, flyf_id: str = None,
                                      limit: int = 20) -> dict:
        """Semantic search across transcribed podcast episodes (embedding
        similarity over transcript chunks). Results carry the matching chunk's
        time range, a text preview, and a similarity score (0-1).
        `flyf_id` restricts to one podcast; `limit` default 20, max 100."""
        return await self._c._get("/audio/episodes/search",
                                  {"q": query, "flyf_id": flyf_id, "limit": limit})

    async def search_podcast_guests(self, query: str, limit: int = 20) -> dict:
        """Search podcast guests/hosts by name (fuzzy). Matches include profile
        details and detected episode appearances with role and speaking time."""
        return await self._c._get("/audio/guests/search", {"q": query, "limit": limit})

    async def get_podcast_mentions(self, entity: str, entity_type: str = None,
                                   flyf_id: str = None, limit: int = 20,
                                   offset: int = 0) -> dict:
        """Find episodes mentioning a person, organization, or location
        (case-insensitive NER over transcripts). Rows include mention counts
        and up to 50 in-episode timestamps; newest first, limit/offset paging.
        `entity_type`: 'person', 'organization', or 'location'."""
        return await self._c._get("/audio/mentions", {
            "entity": entity, "entity_type": entity_type, "flyf_id": flyf_id,
            "limit": limit, "offset": offset,
        })

    async def get_podcast_sponsors(self, company: str = None,
                                   episode_url_hash: str = None,
                                   episode_url: str = None, flyf_id: str = None,
                                   limit: int = 20, offset: int = 0) -> dict:
        """Query the podcast sponsor/ads database. Requires `company` or an
        episode (`episode_url_hash` = SHA1 hex of the full audio URL, or pass
        `episode_url` and the SDK hashes it — see surf_api.episode_url_sha1)."""
        if episode_url and not episode_url_hash:
            episode_url_hash = episode_url_sha1(episode_url)
        if not company and not episode_url_hash:
            raise ValueError(
                "provide at least one of 'company', 'episode_url_hash', or 'episode_url'")
        return await self._c._get("/audio/sponsors", {
            "company": company, "episode_url_hash": episode_url_hash,
            "flyf_id": flyf_id, "limit": limit, "offset": offset,
        })

    # Podcast intelligence — phase 4 (per-episode, retrieval only)
    async def get_fact_checks(self, episode_url: str) -> dict:
        """Stored fact-check results for an episode, in claim order (verdict,
        confidence, explanation, sources per claim; summary counts per
        verdict). Retrieval only; 404 when the episode has no fact checks."""
        return await self._c._get("/audio/fact-checks",
                                  {"episode_url": episode_url})

    async def get_translation(self, episode_url: str, language: str) -> dict:
        """Stored transcript translation for an episode (full transcript,
        timestamped segments, TTS audio when generated). Retrieval only —
        never translates on demand; 404 when no translation exists for the
        language (e.g. 'es', 'pt-BR')."""
        return await self._c._get("/audio/translations",
                                  {"episode_url": episode_url,
                                   "language": language})

    async def get_catch_up(self, episode_url: str,
                           timestamp_seconds: float) -> dict:
        """"What did I miss?" summary of an episode up to a playback position
        (seconds, 0-86400): summary, topics_covered, key_points. Cached
        transcript only — never triggers transcription; 404 when the episode
        has no transcript yet."""
        return await self._c._get("/audio/catch-up",
                                  {"episode_url": episode_url,
                                   "timestamp": timestamp_seconds})

    async def skip_to_topic(self, episode_url: str, topic: str,
                            limit: int = 5) -> dict:
        """Semantic "jump to the part about X" within one episode. Matches
        come back best first with start/end seconds, a text preview, and a
        relevance score; empty matches with ok=true means nothing scored above
        the relevance floor. Cached transcript only; 404 when the episode has
        no transcript yet. limit default 5, max 20."""
        return await self._c._get("/audio/skip-to-topic",
                                  {"episode_url": episode_url, "topic": topic,
                                   "limit": limit})

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

    async def generate_image(self, prompt: str, skip_refiner: bool = False) -> dict:
        """Start AI generation of a feed cover image (Stable Diffusion XL).

        Requires the ``use:ai`` scope. Async submit/poll: returns immediately with
        ``{"key": ..., "url": ..., "status": "pending"}`` — generation runs server-side and can
        take a couple of minutes. Poll :meth:`get_generate_image_status` with ``key``
        until ``done``, then use ``url``. Or call :meth:`generate_image_and_wait` to do
        both. ``skip_refiner`` trades quality for speed.
        """
        return await self._c._post("/media/generate-image", json={"prompt": prompt, "skipRefiner": skip_refiner})

    async def get_generate_image_status(self, key: str) -> dict:
        """Poll a generation job: ``{"status": "pending" | "done" | "failed" | "not_found"}``."""
        return await self._c._get("/media/generate-image/status", {"key": key})

    async def generate_image_and_wait(self, prompt: str, skip_refiner: bool = False,
                                       poll_interval: float = 4.0, timeout: float = 600.0) -> dict:
        """Submit a generation job and poll until done, returning ``{"url": ...}``.

        Polls every ``poll_interval`` seconds up to ``timeout`` seconds. Raises
        :class:`SurfAPIError` if generation fails or times out.
        """
        import asyncio
        import time as _time
        submit = await self.generate_image(prompt, skip_refiner=skip_refiner)
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            await asyncio.sleep(poll_interval)
            status = (await self.get_generate_image_status(submit["key"])).get("status")
            if status == "done":
                return {"url": submit["url"]}
            if status in ("failed", "not_found"):
                raise SurfAPIError(f"Image generation {status}", status_code=502)
        raise SurfAPIError("Image generation timed out", status_code=504)


# ==========================================================================
# RTB (Real-Time Bidding) — async
# ==========================================================================

class AsyncSurfRTBClient:
    """Async client for the Surf RTB (Real-Time Bidding) API (uses httpx).

    Mirrors the sync :class:`SurfRTBClient` surface. Targets the RTB endpoints
    at /devportal/v1/rtb/* on ``surf.social`` (distinct from the main API host).
    The API key must include rtb:* scopes.

    Use as an async context manager for proper connection cleanup::

        async with AsyncSurfRTBClient("surf_sk_live_...") as rtb:
            # Sandbox mode -- test without real spend / no publisher config needed
            response = await rtb.bid({
                "id": "req-1",
                "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}],
            }, sandbox=True)

            reports = await rtb.reports(days=7)
            config = await rtb.config()
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://surf.social",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/devportal/v1/rtb",
            headers={
                "X-API-Key": api_key,
                # Content-Type is set per-request by `json=` only when a body is
                # present, so GETs don't send it (mirrors AsyncSurfClient).
                "Accept": "application/json",
                "User-Agent": "surf-api-python-async/1.0.0",
            },
            timeout=timeout,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        """Close the underlying httpx client."""
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an RTB request with retry on 429 (Retry-After) and 5xx,
        using capped exponential backoff — mirrors AsyncSurfClient._request."""
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 429 and attempt < self.max_retries:
                    retry_after = int(resp.headers.get("retry-after", 2 ** attempt))
                    await asyncio.sleep(min(retry_after, 60))
                    continue
                if resp.status_code >= 500 and attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 60))
                    continue
                return self._check(resp)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exc = e
                if attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 60))
                    continue
                raise SurfAPIError(
                    f"Connection failed after {self.max_retries + 1} attempts: {e}",
                    status_code=0,
                    error_code="connection_error",
                )
        if last_exc:
            raise last_exc
        return {}

    def _check(self, resp: httpx.Response) -> dict:
        if resp.status_code == 401:
            raise SurfAuthError("RTB authentication failed (401). Check your API key and rtb:* scopes.", status_code=401)
        if resp.status_code == 403:
            raise SurfScopeError("RTB forbidden (403). Your API key may lack the required rtb:* scope.", status_code=403)
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "5")
            raise SurfRateLimitError(f"Rate limited (429). Retry after {retry_after}s.", retry_after=retry_after, status_code=429)
        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("error_description") or body.get("error") or resp.text[:200]
            except Exception:
                msg = resp.text[:200]
            raise SurfAPIError(msg, status_code=resp.status_code)
        # 204 No Content (e.g. no-bid) or empty body -> no JSON to parse.
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    async def bid(self, request: dict, sandbox: bool = False) -> dict:
        """Send an OpenRTB 2.5 bid request.

        Args:
            request: OpenRTB bid request dict. Must include 'id' and 'imp'.
            sandbox: If True, sets test=1 to get synthetic bids without real spend.

        Returns:
            OpenRTB bid response dict with seatbid array.
        """
        if sandbox:
            request = {**request, "test": 1}
        return await self._request("POST", "/bid", json=request)

    async def reports(self, days: int = 30, granularity: str = "day", app_id: int = None) -> dict:
        """Get RTB performance reports.

        Args:
            days: Number of days (1-90, default 30).
            app_id: Application ID (optional, defaults to first app).
            granularity: 'hour' or 'day'.

        Returns:
            Dict with 'summary' and 'timeseries' keys.
        """
        params = {"days": days, "granularity": granularity}
        if app_id is not None:
            params["app_id"] = app_id
        return await self._request("GET", "/reports", params=params)

    async def config(self, app_id: int = None) -> dict:
        """Get RTB configuration and tier info.

        Returns:
            Dict with 'config' and 'tiers' keys.
        """
        params = {}
        if app_id is not None:
            params["app_id"] = app_id
        return await self._request("GET", "/config", params=params)

    async def scopes(self) -> list:
        """List available RTB scopes."""
        return (await self._request("GET", "/scopes")).get("scopes", [])

    async def ads_txt(self, app_id: str = None) -> dict:
        """Get your personalized ads.txt entry for authorizing Surf as a seller.

        Add the returned `entries` to the ads.txt file at the root of each
        domain where you display Surf ads.

        Returns:
            Dict with 'seller_id', 'entries', 'sellers_json_url', 'instructions'.
        """
        params = {}
        if app_id is not None:
            params["app_id"] = app_id
        return await self._request("GET", "/ads-txt", params=params)


class _AsyncDiagnosticsAPI:
    """Async self-service diagnostics and confidential debug-bundle sharing.

    Mirrors :class:`surf_api.client._DiagnosticsAPI`. See ``client.diagnostics``
    for usage.
    """

    def __init__(self, c: AsyncSurfClient):
        self._c = c

    async def diagnose(self, app_id: str = None) -> dict:
        """Structured diagnosis. With an app API key, omit `app_id` to diagnose
        that token's own app."""
        path = f"/applications/{quote(app_id, safe='')}/diagnose" if app_id else "/diagnose"
        return await self._c._dp_get(path)

    async def create_bundle(self, app_id: str = None, ttl_minutes: int = 15) -> dict:
        """Mint a redacted, expiring debug bundle. Returns share_token + share_url."""
        path = f"/applications/{quote(app_id, safe='')}/debug-bundle" if app_id else "/debug-bundle"
        return await self._c._dp_post(path, json={"ttl_minutes": ttl_minutes})

    async def get_bundle(self, token: str) -> dict:
        """Fetch a shared bundle by its share token (no auth required)."""
        return await self._c._dp_get(f"/debug-bundle/{quote(token, safe='')}")

    async def revoke_bundle(self, token: str) -> dict:
        """Revoke a bundle you minted before it expires."""
        return await self._c._dp_delete(f"/debug-bundle/{quote(token, safe='')}")


def _clean(params: Optional[dict]) -> Optional[dict]:
    """Remove None values from params dict."""
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
