"""Surf API client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional
from urllib.parse import quote

import requests

from .exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
    SurfScopeError,
)

DEFAULT_BASE_URL = "https://api.surf.social"
# Internal path prefix — the SDK handles this automatically.
# Users only need to set the base URL (e.g., "https://api.surf.social").
API_PREFIX = "/v1"

# Developer-portal endpoints (diagnostics, debug bundles) live on a different
# host/prefix than the v1 data API. Overridable for non-prod backends.
DEFAULT_DEVPORTAL_URL = "https://surf.social/devportal/v1"


class RateLimitInfo:
    """Rate limit information from response headers."""

    def __init__(self, headers: dict):
        self.limit = int(headers.get("X-RateLimit-Limit", 0))
        self.remaining = int(headers.get("X-RateLimit-Remaining", 0))
        self.reset = headers.get("X-RateLimit-Reset")

    def __repr__(self):
        return f"RateLimitInfo(remaining={self.remaining}/{self.limit}, reset={self.reset})"


class SurfClient:
    """Client for the Surf API.

    Usage::

        from surf_api import SurfClient

        client = SurfClient("surf_sk_live_your_token_here")

        # Get feed metadata
        feed = client.feeds.get("surf/topic/technology")

        # Get posts
        posts = client.feeds.get_posts("surf/topic/technology", limit=20)

        # Search
        results = client.search.feeds("artificial intelligence")

        # AI features
        summary = client.ai.feed_summary("surf/topic/technology")
        answer = client.ai.ask("feeds about sustainable energy")

        # Content analysis
        topics = client.content.topics("https://example.com/article")
        enrichment = client.content.enrich("at://did:plc:.../app.bsky.feed.post/...")

        # Image processing
        info = client.images.info("https://example.com/photo.jpg")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
        max_retries: int = 3,
        devportal_url: str = DEFAULT_DEVPORTAL_URL,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.devportal_url = (devportal_url or DEFAULT_DEVPORTAL_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit: Optional[RateLimitInfo] = None

        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "surf-api-python/1.0.0",
        })

        # Sub-clients
        self.feeds = _FeedsAPI(self)
        self.search = _SearchAPI(self)
        self.ai = _AIAPI(self)
        self.account = _AccountAPI(self)
        self.content = _ContentAPI(self)
        self.images = _ImagesAPI(self)
        self.audio = _AudioAPI(self)
        self.notifications = _NotificationsAPI(self)
        self.preferences = _PreferencesAPI(self)
        self.custom_feeds = _CustomFeedsAPI(self)
        self.media = _MediaAPI(self)
        self.longform = _LongformAPI(self)
        self.diagnostics = _DiagnosticsAPI(self)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{API_PREFIX}{path}"

    def _request(self, method: str, path: str, absolute: bool = False, **kwargs) -> dict:
        kwargs.setdefault("timeout", self.timeout)
        url = path if absolute else self._url(path)
        import time as _time
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(method, url, **kwargs)
                # Only update from responses that actually carry rate-limit
                # headers — devportal (diagnostics) responses omit them and would
                # otherwise clobber the last real data-API rate_limit with zeros.
                if "X-RateLimit-Limit" in resp.headers:
                    self.rate_limit = RateLimitInfo(resp.headers)
                if resp.status_code == 429 and attempt < self.max_retries:
                    retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                    _time.sleep(min(retry_after, 60))
                    continue
                if resp.status_code >= 500 and attempt < self.max_retries:
                    _time.sleep(2 ** attempt)
                    continue
                self._check_errors(resp)
                if resp.status_code == 204:
                    return {}
                return resp.json()
            except (requests.ConnectionError, requests.Timeout) as e:
                last_exc = e
                if attempt < self.max_retries:
                    _time.sleep(2 ** attempt)
                    continue
                raise SurfAPIError(f"Connection failed after {self.max_retries + 1} attempts: {e}",
                                   status_code=0, error_code="connection_error")
        # Should not reach here, but just in case
        if last_exc:
            raise last_exc
        return {}

    def _request_raw(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make a request and return the raw Response (for binary/text responses)."""
        kwargs.setdefault("timeout", self.timeout)
        resp = self._session.request(method, self._url(path), **kwargs)
        self.rate_limit = RateLimitInfo(resp.headers)
        self._check_errors(resp)
        return resp

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._request("GET", path, params=_clean(params))

    def _post(self, path: str, json: Optional[dict] = None, **kwargs) -> dict:
        return self._request("POST", path, json=json, **kwargs)

    def _put(self, path: str, json: Optional[dict] = None) -> dict:
        return self._request("PUT", path, json=json)

    def _patch(self, path: str, json: Optional[dict] = None) -> dict:
        return self._request("PATCH", path, json=json)

    def _delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    # Developer-portal helpers (diagnostics, debug bundles) — different host.
    def _dp_get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._request("GET", f"{self.devportal_url}{path}", absolute=True, params=_clean(params))

    def _dp_post(self, path: str, json: Optional[dict] = None) -> dict:
        return self._request("POST", f"{self.devportal_url}{path}", absolute=True, json=json)

    def _dp_delete(self, path: str) -> dict:
        return self._request("DELETE", f"{self.devportal_url}{path}", absolute=True)

    def _check_errors(self, resp: requests.Response):
        if resp.ok:
            return
        try:
            body = resp.json()
        except Exception:
            body = {}
        msg = body.get("error_description") or body.get("error") or resp.text
        kwargs = dict(
            status_code=resp.status_code,
            error_code=body.get("error"),
            response=resp,
        )
        if resp.status_code == 401:
            raise SurfAuthError(msg, **kwargs)
        if resp.status_code == 403:
            raise SurfScopeError(msg, **kwargs)
        if resp.status_code == 404:
            raise SurfNotFoundError(msg, **kwargs)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise SurfRateLimitError(msg, retry_after=retry_after, **kwargs)
        raise SurfAPIError(msg, **kwargs)

    def paginate(self, path: str, key: str, params: Optional[dict] = None, limit: Optional[int] = None) -> Iterator[Any]:
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
            data = self._get(path, params)
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

    # Private alias for backward compatibility
    _paginate = paginate


# ==========================================================================
# Feeds
# ==========================================================================

class _FeedsAPI:
    """Feed operations (read:feeds scope)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def get(self, surf_id: str) -> dict:
        """Get feed metadata."""
        return self._c._get("/feed", {"surf_id": surf_id})

    def get_posts(self, surf_id: str, limit: int = 20, cursor: str = None,
                  sort: str = None, services: str = None, since: str = None) -> dict:
        """Get posts from a feed.

        `since`: recency cutoff for a digest — a rolling duration ('24h', '7d', '30m', '90s',
        or a bare number of seconds) or an absolute ISO 8601 timestamp; only posts created at
        or after the cutoff are returned.
        """
        return self._c._get("/feed/posts", {
            "surf_id": surf_id, "limit": limit, "cursor": cursor,
            "sort": sort, "services": services, "since": since,
        })

    def iter_posts(self, surf_id: str, limit: int = None, page_size: int = 40,
                   sort: str = None, services: str = None) -> Iterator[dict]:
        """Auto-paginate through all posts in a feed.

        Yields individual post dicts. Stops when no more results or `limit` is reached.

        Args:
            surf_id: Feed ID
            limit: Max total posts to yield (None = no limit)
            page_size: Posts per API call (default 40)
            sort: Sort order (recent or top)
            services: Filter by service (mastodon, bluesky, rss)
        """
        cursor = None
        fetched = 0
        while True:
            data = self.get_posts(surf_id, limit=page_size, cursor=cursor,
                                  sort=sort, services=services)
            posts = data if isinstance(data, list) else data.get("posts", data) if isinstance(data, dict) else []
            if isinstance(posts, dict):
                posts = list(posts.values()) if posts else []
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

    def get_post(self, post_id: str, thread: bool = False) -> dict:
        """Get a single post by ID, optionally with thread context."""
        return self._c._get("/post", {"id": post_id, "thread": str(thread).lower()})

    def get_following(self, limit: int = 50) -> dict:
        """Get feeds the authenticated user follows."""
        return self._c._get("/feed/following", {"limit": limit})

    def get_speeddial(self) -> dict:
        """Get the user's speed dial feeds."""
        return self._c._get("/feed/speeddial")

    def get_rss(self, surf_id: str) -> str:
        """Get RSS XML for a feed."""
        resp = self._c._request_raw("GET", "/feed/posts",
                                     params={"surf_id": surf_id, "format": "rss"})
        return resp.text

    # Write operations (require write:statuses scope)

    def create_post(self, status: str, visibility: str = "public",
                    in_reply_to_id: str = None, sensitive: bool = False,
                    spoiler_text: str = None, language: str = None,
                    service: str = None) -> dict:
        """Create a new post (write:statuses). Use OAuth token for user-delegated posting.

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        body = {"status": status, "visibility": visibility}
        if in_reply_to_id:
            body["in_reply_to_id"] = in_reply_to_id
        if sensitive:
            body["sensitive"] = True
        if spoiler_text:
            body["spoiler_text"] = spoiler_text
        if language:
            body["language"] = language
        path = "/statuses"
        if service:
            path += f"?service={service}"
        return self._c._post(path, json=body)

    def favourite(self, post_id: str, service: str = None) -> dict:
        """Favorite a post (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/statuses/{quote(post_id, safe='')}/favourite"
        if service:
            path += f"?service={service}"
        return self._c._post(path)

    def unfavourite(self, post_id: str, service: str = None) -> dict:
        """Unfavorite a post (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/statuses/{quote(post_id, safe='')}/unfavourite"
        if service:
            path += f"?service={service}"
        return self._c._post(path)

    def boost(self, post_id: str, service: str = None) -> dict:
        """Boost/reblog a post (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/statuses/{quote(post_id, safe='')}/reblog"
        if service:
            path += f"?service={service}"
        return self._c._post(path)

    def unboost(self, post_id: str, service: str = None) -> dict:
        """Unboost a post (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/statuses/{quote(post_id, safe='')}/unreblog"
        if service:
            path += f"?service={service}"
        return self._c._post(path)

    def bookmark(self, post_id: str, service: str = None) -> dict:
        """Bookmark a post (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/statuses/{quote(post_id, safe='')}/bookmark"
        if service:
            path += f"?service={service}"
        return self._c._post(path)

    def unbookmark(self, post_id: str, service: str = None) -> dict:
        """Unbookmark a post (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/statuses/{quote(post_id, safe='')}/unbookmark"
        if service:
            path += f"?service={service}"
        return self._c._post(path)

    def delete_post(self, post_id: str, service: str = None) -> dict:
        """Delete own post (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/statuses/{quote(post_id, safe='')}"
        if service:
            path += f"?service={service}"
        return self._c._delete(path)


# ==========================================================================
# Search
# ==========================================================================

class _SearchAPI:
    """Search operations (read:search scope). Each type maps to its own endpoint."""

    _PATHS = {
        "posts": "/search/posts",
        "feeds": "/search/maestra/feeds",
        "accounts": "/search/bluesky/searchActors",
        "podcasts": "/search/maestra/feeds",
        "rss": "/search/rss/search",
    }

    def __init__(self, client: SurfClient):
        self._c = client

    def search(self, query: str, type: str = "feeds", limit: int = 20, sort: str = None,
               since: str = None, automated: bool = None, safety: str = None,
               exclude_replies: bool = None) -> dict:
        """Search. type: feeds, posts, accounts, podcasts, rss.

        Post-only options (ignored for other types):
          sort: 'recent' (newest-first), 'top' (relevance/engagement), or omit.
          since: recency window, e.g. '24h', '7d', '30m', '90s'. Pair with sort='top'
                 for a "recent AND engaged" (trending) result.
          automated: False drops bot/bridge-account posts server-side.
          safety: 'sfw' drops posts flagged NSFW at ingest, applied server-side before
                  the limit so you get a full page of safe posts. 'all' returns everything.
          exclude_replies: True drops replies into other threads, keeping standalone and
                  quote posts.
        """
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
        return self._c._get(path, params)

    def feeds(self, query: str, limit: int = 20) -> dict:
        """Search for feeds."""
        return self.search(query, type="feeds", limit=limit)

    def posts(self, query: str, limit: int = 20, sort: str = None,
              since: str = None, automated: bool = None, safety: str = None,
              exclude_replies: bool = None) -> dict:
        """Search for posts. `query` supports exact phrases in double quotes
        ('"climate change"') and boolean operators AND/&& and OR/|| between terms
        ('cats AND dogs'); the word forms are uppercase-only, plain keywords are
        implicit AND. `sort`: 'recent' newest-first, 'top' relevance/engagement.
        `since`: recency window ('24h', '7d', …); pair with sort='top' for trending.
        `automated`: False drops bot/bridge-account posts.
        `safety`: 'sfw' drops NSFW-flagged posts server-side; 'all' returns everything.
        `exclude_replies`: True drops replies into other threads."""
        return self.search(query, type="posts", limit=limit, sort=sort,
                           since=since, automated=automated, safety=safety,
                           exclude_replies=exclude_replies)

    def accounts(self, query: str, limit: int = 20) -> dict:
        """Search for accounts."""
        return self.search(query, type="accounts", limit=limit)

    def podcasts(self, query: str, limit: int = 20) -> dict:
        """Search for podcasts."""
        return self.search(query, type="podcasts", limit=limit)

    def publications(self, q: str, count: int = 20, offset: int = 0) -> list:
        """Search for longform publications (standard.site / Leaflet).

        Returns a list of publication dicts (uri, name, description, icon_url,
        publisher handle/avatar). ``offset`` maps to the API's ``from`` query
        parameter (``from`` is reserved in Python).
        """
        return self._c._get("/search/publications", {"q": q, "count": count, "from": offset})

    def discover(self, type: str = "recommended", surf_id: str = None, limit: int = 20) -> dict:
        """Discover feeds. type: recommended, similar, interests."""
        return self._c._get("/search/discover", {
            "type": type, "surf_id": surf_id, "limit": limit,
        })


# ==========================================================================
# Longform (standard.site / Leaflet documents & publications)
# ==========================================================================

class _LongformAPI:
    """Longform documents & publications — standard.site / Leaflet.

    Document and publication reads require the ``read:feeds`` scope;
    :meth:`search_publications` requires ``read:search``.

    Documents and publications are addressed by AT-URI (e.g.
    ``at://did:plc:x/site.standard.document/3k2a``). Pass the raw AT-URI —
    the SDK percent-encodes it into the path automatically.
    """

    def __init__(self, client: SurfClient):
        self._c = client

    def document(self, uri: str, format: str = None) -> dict:
        """Get a longform document by AT-URI.

        Args:
            uri: Document AT-URI (raw; encoded internally).
            format: ``'html'`` (default, ``content_html``) or ``'blocks'``
                (``pages``). Omitted from the request when None.
        """
        return self._c._get(f"/documents/{quote(uri, safe='')}", {"format": format})

    def publication(self, uri: str) -> dict:
        """Get a publication by AT-URI.

        Args:
            uri: Publication AT-URI (raw; encoded internally).
        """
        return self._c._get(f"/publications/{quote(uri, safe='')}")

    def publication_documents(self, uri: str, tags: Optional[List[str]] = None,
                              count: int = 20, offset: int = 0) -> list:
        """List a publication's documents (newest first).

        Args:
            uri: Publication AT-URI (raw; encoded internally).
            tags: Optional list of tags to filter by (repeatable param).
            count: Page size (default 20, max 100).
            offset: Result offset; maps to the API's ``from`` query parameter
                (``from`` is reserved in Python).
        """
        return self._c._get(f"/publications/{quote(uri, safe='')}/documents", {
            "tags": tags, "count": count, "from": offset,
        })

    def search_publications(self, q: str, count: int = 20, offset: int = 0) -> list:
        """Search for publications (read:search scope).

        Args:
            q: Search query (required).
            count: Page size (default 20, max 100).
            offset: Result offset; maps to the API's ``from`` query parameter.
        """
        return self._c._get("/search/publications", {"q": q, "count": count, "from": offset})


# ==========================================================================
# AI (requires use:ai scope, 10/day rate limit)
# ==========================================================================

class _AIAPI:
    """AI-powered features (use:ai scope, 10 requests/day)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def ask(self, query: str, k: int = 10, schema_type: str = None, feed_id: str = None) -> dict:
        """Natural language search powered by NLWeb."""
        return self._c._get("/ai/ask", {
            "query": query, "k": k, "schema_type": schema_type, "feed_id": feed_id,
        })

    def feed_summary(self, surf_id: str, limit: int = 20) -> dict:
        """Get an AI-generated summary of a feed's recent posts."""
        return self._c._get("/ai/feed-summary", {"surf_id": surf_id, "limit": limit})

    def thread_summary(self, post_at: str) -> dict:
        """Get an AI-generated summary of a Bluesky post thread."""
        return self._c._get("/ai/thread-summary", {"post_at": post_at})

    def fact_check(self, text: str = None, post_surf_id: str = None,
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
        return self._c._post("/ai/fact-check", json=body)

    def build_feed(self, prompt: str, feed_id: str = None) -> Iterator[str]:
        """Build a custom feed using AI (SSE stream).

        Returns an iterator of Server-Sent Event lines.
        """
        resp = self._c._session.post(
            self._c._url("/ai/feed-builder"),
            json={"prompt": prompt, "feed_id": feed_id},
            stream=True,
            timeout=60,
        )
        self._c.rate_limit = RateLimitInfo(resp.headers)
        self._c._check_errors(resp)
        for line in resp.iter_lines():
            if line:
                yield line.decode("utf-8")


# ==========================================================================
# Account
# ==========================================================================

class _AccountAPI:
    """Account operations (read:account / write:account scopes)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def get(self) -> dict:
        """Get the authenticated user's account info."""
        return self._c._get("/account")

    def update(self, **fields) -> dict:
        """Update account fields (write:account)."""
        return self._c._put("/account", json=fields)

    def lookup(self, account: str) -> dict:
        """Look up an account by handle (e.g. user.bsky.social or user@mastodon.social)."""
        return self._c._get("/account/lookup", {"account": account})

    def get_links(self) -> dict:
        """Get all profile links."""
        return self._c._get("/account/links")

    def add_link(self, title: str, url: str, icon: str = None) -> dict:
        """Add a profile link (write:account)."""
        body = {"title": title, "url": url}
        if icon:
            body["icon"] = icon
        return self._c._post("/account/links", json=body)

    def update_link(self, link_id: str, **fields) -> dict:
        """Update a profile link (write:account)."""
        fields["id"] = link_id
        return self._c._put(f"/account/links/{link_id}", json=fields)

    def delete_link(self, link_id: str) -> dict:
        """Delete a profile link (write:account)."""
        return self._c._delete(f"/account/links/{link_id}")

    def follow(self, account_id: str, service: str = None) -> dict:
        """Follow an account (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/accounts/{account_id}/follow"
        if service:
            path += f"?service={service}"
        return self._c._post(path)

    def unfollow(self, account_id: str, service: str = None) -> dict:
        """Unfollow an account (write:statuses).

        Args:
            service: Optional target service ('bluesky' or 'mastodon').
        """
        path = f"/accounts/{account_id}/unfollow"
        if service:
            path += f"?service={service}"
        return self._c._post(path)

    def get_connected_apps(self) -> dict:
        """Get OAuth-authorized third-party apps (read:account)."""
        return self._c._get("/account/connected-apps")

    def revoke_connected_app(self, authorization_id: int) -> dict:
        """Revoke a third-party app's OAuth access (write:account)."""
        return self._c._post(f"/account/connected-apps/{authorization_id}/revoke")


# ==========================================================================
# Content
# ==========================================================================

class _ContentAPI:
    """Content processing (read:feeds scope)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def resolve(self, url: str) -> dict:
        """Resolve/unshorten a URL. Returns final URL and redirect chain."""
        return self._c._get("/content/resolve", {"url": url})

    def extract(self, url: str, type: str = "article") -> dict:
        """Extract structured content from a URL (article, image, video, audio)."""
        return self._c._get("/content/extract", {"url": url, "type": type})

    def language(self, url: str) -> dict:
        """Detect the language of content at a URL."""
        return self._c._get("/content/language", {"url": url})

    def topics(self, url: str) -> dict:
        """Get auto-assigned topics for a URL."""
        return self._c._get("/content/topics", {"url": url})

    def enrich(self, post_id: str) -> dict:
        """Get full enrichment data for a post (topics, claim_score, NSFW, etc.)."""
        return self._c._get("/content/enrich", {"post_id": post_id})


# ==========================================================================
# Images
# ==========================================================================

class _ImagesAPI:
    """Image processing (read:feeds scope)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def info(self, url: str) -> dict:
        """Get image dimensions and size variant URLs."""
        return self._c._get("/image/info", {"url": url})

    def resize(self, url: str, size: str = "medium") -> bytes:
        """Resize an image. size: small (240px), medium (500px), large (1024px), xlarge (2048px).
        Returns raw image bytes.
        """
        resp = self._c._request_raw("GET", "/image/resize", params={"url": url, "size": size})
        return resp.content

    def colors(self, url: str, k: int = 5) -> bytes:
        """Extract dominant color palette. Returns image bytes of the palette visualization."""
        resp = self._c._request_raw("GET", "/image/colors", params={"url": url, "k": k})
        return resp.content

    def moderate(self, url: str) -> dict:
        """Check an image for NSFW content. Returns nsfw flag and moderation labels."""
        return self._c._get("/image/moderate", {"url": url})


# ==========================================================================
# Audio
# ==========================================================================

class _AudioAPI:
    """Audio operations (read:audio / write:audio scopes)."""

    def __init__(self, client: SurfClient):
        self._c = client

    # Radio
    def list_stations(self) -> dict:
        """List radio stations for the authenticated user."""
        return self._c._get("/audio/radio/stations")

    def get_station(self, station_id: str) -> dict:
        """Get a radio station by ID."""
        return self._c._get(f"/audio/radio/stations/{station_id}")

    def create_station(self, feed_surf_id: str, title: str = None) -> dict:
        """Create a radio station from a feed (write:audio)."""
        body = {"feed_surf_id": feed_surf_id}
        if title:
            body["title"] = title
        return self._c._post("/audio/radio/stations", json=body)

    def generate_program(self, station_id: str) -> dict:
        """Generate a new radio program (write:audio)."""
        return self._c._post(f"/audio/radio/stations/{station_id}/generate")

    def get_program(self, program_id: str) -> dict:
        """Get a radio program manifest with signed audio URLs."""
        return self._c._get(f"/audio/radio/programs/{program_id}")

    # Briefing
    def generate_briefing(self) -> dict:
        """Generate a new daily briefing (write:audio)."""
        return self._c._post("/audio/briefing/generate")

    def get_briefing(self, briefing_id: str = None) -> dict:
        """Get a briefing. If no ID, returns latest."""
        if briefing_id:
            return self._c._get(f"/audio/briefing/{briefing_id}")
        return self._c._get("/audio/briefing/latest")

    # Transcript
    def get_transcript(self, episode_url: str) -> dict:
        """Get a signed URL for an episode transcript."""
        return self._c._get("/audio/transcript", {"episode_url": episode_url})

    def get_show_notes(self, episode_url: str, language: str = None) -> dict:
        """Get structured, AI-generated show notes for a transcribed episode.

        Returns summary, topics, people, organizations, a timestamped outline,
        key takeaways, and chapters, plus a ``signed_url`` for the raw
        show-notes JSON. Raises :class:`SurfNotFoundError` if show notes have
        not been generated for the episode yet.

        Args:
            episode_url: The episode's audio/enclosure URL.
            language: Optional language code (e.g. ``'en'``, ``'es'``) for
                translated show notes; omit for the original language.
        """
        return self._c._get("/audio/transcripts/show-notes",
                            {"episode_url": episode_url, "language": language})

    # Podcast intelligence
    def search_podcast_episodes(self, query: str, flyf_id: str = None,
                                limit: int = 20) -> dict:
        """Semantic search across transcribed podcast episodes.

        Finds episodes matching a natural-language ``query`` using embedding
        similarity over transcript chunks (no keyword overlap required). Each
        result identifies the matching chunk (``chunk_start_seconds`` /
        ``chunk_end_seconds``) with a text ``preview`` and is ordered by
        similarity ``score`` (0-1). Results carry ``episode_url_hash`` (SHA1
        hex of the full audio URL — the episode's stable ID across the audio
        APIs; see :func:`episode_url_sha1`).

        Args:
            query: Natural language search query (max 512 chars).
            flyf_id: Restrict to one podcast (SHA1 hex of the full RSS feed URL).
            limit: Maximum results (default 20, max 100).
        """
        return self._c._get("/audio/episodes/search",
                            {"q": query, "flyf_id": flyf_id, "limit": limit})

    def search_podcast_guests(self, query: str, limit: int = 20) -> dict:
        """Search podcast guests and hosts by name (fuzzy matching).

        Each match includes the person's known profile details (title,
        organization, social handles) and their detected episode
        ``appearances`` with role, confidence, and speaking time.

        Args:
            query: Guest name or partial name (max 512 chars).
            limit: Maximum guests (default 20, max 100).
        """
        return self._c._get("/audio/guests/search", {"q": query, "limit": limit})

    def get_podcast_mentions(self, entity: str, entity_type: str = None,
                             flyf_id: str = None, limit: int = 20,
                             offset: int = 0) -> dict:
        """Find podcast episodes mentioning a person, organization, or location.

        Backed by named-entity recognition over episode transcripts; matching
        is case-insensitive. Each row covers one episode and includes the
        mention count, the first mention time, and up to 50 mention
        ``timestamps`` (``{start, end}`` in seconds) for deep-linking.
        Newest episodes first; paginate with ``limit``/``offset``.

        Args:
            entity: Entity name to look up (case-insensitive, max 512 chars).
            entity_type: Optional filter: 'person', 'organization', or 'location'.
            flyf_id: Restrict to one podcast (SHA1 hex of the full RSS feed URL).
            limit: Maximum rows (default 20, max 100).
            offset: Pagination offset (max 10000).
        """
        return self._c._get("/audio/mentions", {
            "entity": entity, "entity_type": entity_type, "flyf_id": flyf_id,
            "limit": limit, "offset": offset,
        })

    def get_podcast_sponsors(self, company: str = None,
                             episode_url_hash: str = None,
                             episode_url: str = None, flyf_id: str = None,
                             limit: int = 20, offset: int = 0) -> dict:
        """Query the podcast sponsor/ads database.

        Each row is one detected ad placement in one episode: advertiser,
        product, category, format, promo code, exact time range, and a text
        preview of the ad read. Search by ``company`` (case-insensitive,
        newest placements first) or list all ads in a single episode via
        ``episode_url_hash`` (SHA1 hex of the full audio URL) or the
        convenience ``episode_url`` (hashed for you); at least one of the
        three is required — combine company + episode to check whether a
        company advertised in a specific episode.

        Args:
            company: Sponsor company name (case-insensitive, max 512 chars).
            episode_url_hash: SHA1 hex (40 chars) of the episode's full audio URL.
            episode_url: The episode's full audio URL; the SDK hashes it into
                ``episode_url_hash`` (ignored when the hash is passed directly).
            flyf_id: Restrict to one podcast (SHA1 hex of the full RSS feed URL).
            limit: Maximum rows (default 20, max 100).
            offset: Pagination offset (max 10000).
        """
        if episode_url and not episode_url_hash:
            episode_url_hash = episode_url_sha1(episode_url)
        if not company and not episode_url_hash:
            raise ValueError(
                "provide at least one of 'company', 'episode_url_hash', or 'episode_url'")
        return self._c._get("/audio/sponsors", {
            "company": company, "episode_url_hash": episode_url_hash,
            "flyf_id": flyf_id, "limit": limit, "offset": offset,
        })

    # Podcast intelligence — phase 4 (per-episode, retrieval only)
    def get_fact_checks(self, episode_url: str) -> dict:
        """Get stored fact-check results for an episode, in claim order.

        Each claim carries the claim text/type, where it's made in the episode
        (``timestamp_seconds``), a ``verdict`` with ``confidence`` and
        ``explanation``, plus the ``sources`` and ``search_queries`` behind
        the verdict; the ``summary`` object counts claims per verdict.
        Retrieval only — never triggers a new fact-check run. Raises
        :class:`SurfNotFoundError` when the episode has no fact checks.

        Args:
            episode_url: The episode's full audio/enclosure URL.
        """
        return self._c._get("/audio/fact-checks", {"episode_url": episode_url})

    def get_translation(self, episode_url: str, language: str) -> dict:
        """Get a stored transcript translation for an episode.

        Returns the full ``translated_transcript``, timestamped
        ``translated_segments``, and — when TTS was generated — a translated
        ``audio_url`` with duration and voice, under the ``translation`` key.
        Retrieval only — never translates on demand. Raises
        :class:`SurfNotFoundError` when no stored translation exists for the
        language.

        Args:
            episode_url: The episode's full audio/enclosure URL.
            language: Target language code (e.g. ``'es'``, ``'pt-BR'``).
        """
        return self._c._get("/audio/translations",
                            {"episode_url": episode_url, "language": language})

    def get_catch_up(self, episode_url: str, timestamp_seconds: float) -> dict:
        """"What did I miss?" — summarize an episode up to a playback position.

        Returns a prose ``summary`` plus ``topics_covered``, ``key_points``,
        and ``missed_duration_seconds`` for everything before the timestamp.
        Works from the episode's cached transcript only and never triggers
        transcription — raises :class:`SurfNotFoundError` (error
        ``"transcript not available"``) when the episode has no transcript
        yet.

        Args:
            episode_url: The episode's full audio/enclosure URL.
            timestamp_seconds: Playback position to catch up to, in seconds
                (0-86400).
        """
        return self._c._get("/audio/catch-up",
                            {"episode_url": episode_url,
                             "timestamp": timestamp_seconds})

    def skip_to_topic(self, episode_url: str, topic: str, limit: int = 5) -> dict:
        """Semantic "jump to the part about X" within one episode.

        Finds the transcript passages most relevant to ``topic`` via embedding
        similarity (no keyword overlap required). ``matches`` come back best
        first, each with ``start_seconds``/``end_seconds`` for deep-linking, a
        ``text_preview``, and a relevance ``score``; an empty ``matches`` list
        with ``ok: true`` means nothing in the episode scored above the
        relevance floor. Works from the cached transcript only and never
        triggers transcription — raises :class:`SurfNotFoundError` when the
        episode has no transcript yet.

        Args:
            episode_url: The episode's full audio/enclosure URL.
            topic: Topic/subject to jump to, in natural language (max 512 chars).
            limit: Maximum matches (default 5, max 20).
        """
        return self._c._get("/audio/skip-to-topic",
                            {"episode_url": episode_url, "topic": topic,
                             "limit": limit})

    # Quiz
    def get_daily_quiz(self) -> dict:
        """Get the daily quiz questions."""
        return self._c._get("/audio/quiz/daily")

    # TTS
    def text_to_speech(self, text: str, voice: str = "en-US-AriaNeural") -> bytes:
        """Convert text to speech (write:audio). Returns MP3 bytes."""
        resp = self._c._request_raw("POST", "/audio/tts",
                                     json={"text": text, "voice": voice})
        return resp.content


# ==========================================================================
# Notifications
# ==========================================================================

class _NotificationsAPI:
    """Notification operations (read:notifications scope)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def list(self, limit: int = 30, cursor: str = None, type: str = None) -> dict:
        """Get notifications. type: 'activity' for social activity."""
        return self._c._get("/notifications", {"limit": limit, "cursor": cursor, "type": type})

    def mark_read(self) -> dict:
        """Mark notifications as read / reset badge count."""
        return self._c._post("/notifications/read")


# ==========================================================================
# Preferences
# ==========================================================================

class _PreferencesAPI:
    """Preference operations (read:preferences / write:preferences scopes)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def get(self) -> dict:
        """Get user preferences."""
        return self._c._get("/preferences/account")

    def update(self, **preferences) -> dict:
        """Update user preferences (write:preferences). Merge-patch semantics."""
        return self._c._patch("/preferences/account", json=preferences)


# ==========================================================================
# Custom Feeds
# ==========================================================================

class FeedTheme:
    """Helper to build a feed theme for create/update operations.

    Uses semantic color names (``surface``, ``surfaceHeader``, ``surfaceCard``,
    ``onSurface``, ``onHeader``, ``accent``) and separates header/image concerns
    from color concerns.

    Example::

        theme = FeedTheme(
            header_image="https://cdn.example.com/logo.png",
            header_image_size={"width": 600, "height": 272},
            surface="#EFEADD",
            surface_header="#005F5F",
        )
        client.custom_feeds.create("My Feed", theme=theme)
    """

    def __init__(
        self,
        # Header
        header_image: str = None,
        header_image_dark: str = None,
        header_image_size: dict = None,
        header_image_padding: dict = None,
        layout: str = None,
        responsive_compact_image_size: dict = None,
        responsive_compact_image_padding: dict = None,
        # Colors — light
        surface: str = None,
        surface_header: str = None,
        surface_card: str = None,
        on_surface: str = None,
        on_header: str = None,
        accent: str = None,
        extra_light: dict = None,
        # Colors — dark
        surface_dark: str = None,
        surface_header_dark: str = None,
        surface_card_dark: str = None,
        on_surface_dark: str = None,
        on_header_dark: str = None,
        accent_dark: str = None,
        extra_dark: dict = None,
    ):
        self.header_image = header_image
        self.header_image_dark = header_image_dark
        self.header_image_size = header_image_size
        self.header_image_padding = header_image_padding
        self.layout = layout
        self.responsive_compact_image_size = responsive_compact_image_size
        self.responsive_compact_image_padding = responsive_compact_image_padding
        self.surface = surface
        self.surface_header = surface_header
        self.surface_card = surface_card
        self.on_surface = on_surface
        self.on_header = on_header
        self.accent = accent
        self.extra_light = extra_light
        self.surface_dark = surface_dark
        self.surface_header_dark = surface_header_dark
        self.surface_card_dark = surface_card_dark
        self.on_surface_dark = on_surface_dark
        self.on_header_dark = on_header_dark
        self.accent_dark = accent_dark
        self.extra_dark = extra_dark

    def to_dict(self) -> dict:
        """Convert to the ``theme`` dict accepted by the API."""
        theme = {}

        # Header
        header = {}
        if self.header_image:
            header["image"] = self.header_image
        if self.header_image_dark:
            header["imageDark"] = self.header_image_dark
        if self.header_image_size:
            header["imageSize"] = self.header_image_size
        if self.header_image_padding:
            header["imagePadding"] = self.header_image_padding
        if self.layout:
            header["layout"] = self.layout
        if self.responsive_compact_image_size or self.responsive_compact_image_padding:
            compact = {}
            if self.responsive_compact_image_size:
                compact["imageSize"] = self.responsive_compact_image_size
            if self.responsive_compact_image_padding:
                compact["imagePadding"] = self.responsive_compact_image_padding
            header["responsive"] = {"compact": compact}
        if header:
            theme["header"] = header

        # Colors
        colors = {}
        light = {}
        for attr, key in [("surface", "surface"), ("surface_header", "surfaceHeader"),
                          ("surface_card", "surfaceCard"), ("on_surface", "onSurface"),
                          ("on_header", "onHeader"), ("accent", "accent")]:
            val = getattr(self, attr)
            if val:
                light[key] = val
        if self.extra_light:
            light.update(self.extra_light)
        if light:
            colors["light"] = light

        dark = {}
        for attr, key in [("surface_dark", "surface"), ("surface_header_dark", "surfaceHeader"),
                          ("surface_card_dark", "surfaceCard"), ("on_surface_dark", "onSurface"),
                          ("on_header_dark", "onHeader"), ("accent_dark", "accent")]:
            val = getattr(self, attr)
            if val:
                dark[key] = val
        if self.extra_dark:
            dark.update(self.extra_dark)
        if dark:
            colors["dark"] = dark

        if colors:
            theme["colors"] = colors

        return theme


@dataclass
class FeedFilter:
    """A filter applied to a custom-feed operator.

    Args:
        surf_id: SurfId of the source to filter on.
        operator: Filter role (``"source"``, ``"include"``, ``"exclude"``, etc.).
    """

    surf_id: str
    operator: str = "source"

    def to_dict(self) -> dict:
        return {"surfId": self.surf_id, "operator": self.operator}


@dataclass
class NewFeedOperator:
    """Writable shape for a custom-feed operator — the fields the API accepts on create.

    Server-assigned fields (``id``, ``created``, ``last_modified``) are not included.

    Common case::

        NewFeedOperator.source("surf/topic/artificial-intelligence")

    Typed operator::

        NewFeedOperator.of("surf/hashtag/cats", operator="include")
    """

    surf_id: str
    operator: str = "source"
    filters: Optional[List[FeedFilter]] = field(default=None)

    @staticmethod
    def source(surf_id: str) -> "NewFeedOperator":
        """A ``source`` operator for *surf_id* with no filters."""
        return NewFeedOperator(surf_id=surf_id)

    @staticmethod
    def of(surf_id: str, operator: str) -> "NewFeedOperator":
        """An operator of the given role for *surf_id* with no filters."""
        return NewFeedOperator(surf_id=surf_id, operator=operator)

    def to_dict(self) -> dict:
        d: dict = {"surfId": self.surf_id, "operator": self.operator}
        if self.filters:
            d["filters"] = [f.to_dict() for f in self.filters]
        return d


class _CustomFeedsAPI:
    """Custom feed operations (write:feeds scope).

    Uses the public /custom/* paths (rewritten to /builder/surf/custom/* internally).
    """

    def __init__(self, client: SurfClient):
        self._c = client

    def list(self) -> dict:
        """List custom feeds owned by the authenticated user."""
        return self._c._get("/custom")

    def get(self, feed_id: str) -> dict:
        """Get a custom feed by ID."""
        return self._c._get(f"/custom/{feed_id}")

    def create(self, title: str, description: str = None,
               operators: Optional[List] = None,
               theme: FeedTheme = None, image: str = None) -> dict:
        """Create a new custom feed.

        Args:
            title: Feed title (required).
            description: Feed description.
            operators: List of :class:`NewFeedOperator` objects or raw dicts
                defining feed sources.
            theme: Optional FeedTheme to set the feed's visual appearance.
            image: Optional cover image URL (used for share cards / OG tags).
        """
        body: dict = {"title": title}
        if description:
            body["description"] = description
        if operators:
            body["operators"] = [
                op.to_dict() if isinstance(op, NewFeedOperator) else op
                for op in operators
            ]
        if image:
            body["image"] = image
        if theme:
            body["theme"] = theme.to_dict()
        return self._c._post("/custom", json=body)

    def create_with_operators(self, title: str, operators: List[NewFeedOperator],
                              description: str = None) -> dict:
        """Create a new custom feed with typed operator objects.

        Convenience overload that accepts :class:`NewFeedOperator` instances
        instead of raw dicts::

            client.custom_feeds.create_with_operators(
                "AI News",
                operators=[
                    NewFeedOperator.source("surf/topic/artificial-intelligence"),
                    NewFeedOperator.source("surf/hashtag/machinelearning"),
                ],
                description="Latest AI",
            )

        Args:
            title: Feed title (required).
            operators: One or more :class:`NewFeedOperator` instances.
            description: Optional feed description.
        """
        return self.create(title, description=description, operators=operators)

    def update(self, feed_id: str, theme: FeedTheme = None, **kwargs) -> dict:
        """Update a custom feed.

        This is a full-replace operation — omitted fields are cleared.
        Always re-send the complete state you want to preserve.

        Args:
            feed_id: The feed ID.
            theme: Optional FeedTheme to set/update the visual theme.
            **kwargs: Other fields (title, description, visibility, tags, image).
        """
        body = dict(kwargs)
        if theme:
            body["theme"] = theme.to_dict()
        return self._c._put(f"/custom/{feed_id}", json=body)

    def delete(self, feed_id: str) -> dict:
        """Delete a custom feed."""
        return self._c._delete(f"/custom/{feed_id}")

    def clone(self, feed_id: str) -> dict:
        """Clone an existing custom feed."""
        return self._c._post(f"/custom/{feed_id}/clone")

    def publish(self, feed_id: str) -> dict:
        """Publish a custom feed (makes it publicly discoverable)."""
        return self._c._post(f"/custom/{feed_id}/publish")

    def unpublish(self, feed_id: str) -> dict:
        """Unpublish a custom feed."""
        return self._c._post(f"/custom/{feed_id}/unpublish")

    def add_operator(self, feed_id: str, operator: dict) -> dict:
        """Add an operator (source) to a custom feed."""
        return self._c._post(f"/custom/{feed_id}/operators", json=[operator])

    def add_operators(self, feed_id: str, operators: list) -> dict:
        """Add multiple operators to a custom feed."""
        return self._c._post(f"/custom/{feed_id}/operators", json=operators)

    def update_operator(self, feed_id: str, operator_id: str, operator: dict) -> dict:
        """Update an operator in a custom feed."""
        return self._c._put(f"/custom/{feed_id}/operators/{operator_id}", json=operator)

    def remove_operator(self, feed_id: str, operator_id: str) -> dict:
        """Remove an operator from a custom feed."""
        return self._c._delete(f"/custom/{feed_id}/operators/{operator_id}")


# ==========================================================================
# Media
# ==========================================================================

class _MediaAPI:
    """Media operations."""

    def __init__(self, client: SurfClient):
        self._c = client

    def upload(self, file_path: str, content_type: str = "image/jpeg") -> dict:
        """Upload a media file (image)."""
        with open(file_path, "rb") as f:
            resp = self._c._session.post(
                self._c._url("/media/upload"),
                files={"file": (file_path, f, content_type)},
                timeout=self._c.timeout,
            )
        self._c.rate_limit = RateLimitInfo(resp.headers)
        self._c._check_errors(resp)
        return resp.json()

    def generate_image(self, prompt: str, skip_refiner: bool = False) -> dict:
        """Start AI generation of a feed cover image (Stable Diffusion XL).

        Requires the ``use:ai`` scope. Async submit/poll: returns immediately with
        ``{"key": ..., "url": ..., "status": "pending"}`` — generation runs server-side and can
        take a couple of minutes. Poll :meth:`get_generate_image_status` with ``key``
        until ``done``, then use ``url``. Or call :meth:`generate_image_and_wait` to do
        both. ``skip_refiner`` trades quality for speed.
        """
        return self._c._post("/media/generate-image", json={"prompt": prompt, "skipRefiner": skip_refiner})

    def get_generate_image_status(self, key: str) -> dict:
        """Poll a generation job: ``{"status": "pending" | "done" | "failed" | "not_found"}``."""
        return self._c._get("/media/generate-image/status", {"key": key})

    def generate_image_and_wait(self, prompt: str, skip_refiner: bool = False,
                                poll_interval: float = 4.0, timeout: float = 600.0) -> dict:
        """Submit a generation job and poll until done, returning ``{"url": ...}``.

        Polls every ``poll_interval`` seconds up to ``timeout`` seconds. Raises
        :class:`SurfAPIError` if generation fails or times out.
        """
        import time as _time
        submit = self.generate_image(prompt, skip_refiner=skip_refiner)
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            _time.sleep(poll_interval)
            status = self.get_generate_image_status(submit["key"]).get("status")
            if status == "done":
                return {"url": submit["url"]}
            if status in ("failed", "not_found"):
                raise SurfAPIError(f"Image generation {status}", status_code=502)
        raise SurfAPIError("Image generation timed out", status_code=504)


# ==========================================================================
# RTB (Real-Time Bidding)
# ==========================================================================

class SurfRTBClient:
    """Client for the Surf RTB (Real-Time Bidding) API.

    Uses the same API key as SurfClient but targets the RTB endpoints
    at /devportal/v1/rtb/*. The API key must include rtb:* scopes.

    Usage::

        rtb = SurfRTBClient(api_key="surf_sk_live_...")

        # Sandbox mode -- test without real spend
        response = rtb.bid({
            "id": "req-1",
            "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}],
        }, sandbox=True)

        # Production bid
        response = rtb.bid({
            "id": "req-1",
            "imp": [{
                "id": "1",
                "banner": {"w": 300, "h": 250},
                "bidfloor": 0.50,
                "ext": {"surf": {"feed_id": "surf/topic/technology"}},
            }],
            "site": {"domain": "publisher.example.com"},
        })

        # Impression/click/win/billing are fired from the tracker URLs in the
        # bid response (resp["seatbid"][...]["bid"][...]["nurl"]/["burl"] and the
        # adm trackers) — there's no separate event call.

        # Get reports
        reports = rtb.reports(days=7)

        # Get config
        config = rtb.config()
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://surf.social",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers["X-API-Key"] = api_key
        # Content-Type is set per-request by `json=` only when a body is present,
        # so GETs don't send it (mirrors SurfClient).
        self._session.headers["Accept"] = "application/json"
        self._session.headers["User-Agent"] = "surf-api-python/1.0.0"

    def _url(self, path: str) -> str:
        return f"{self.base_url}/devportal/v1/rtb{path}"

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an RTB request with retry on 429 (Retry-After) and 5xx,
        using capped exponential backoff — mirrors SurfClient._request."""
        kwargs.setdefault("timeout", self.timeout)
        import time as _time
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(method, self._url(path), **kwargs)
                if resp.status_code == 429 and attempt < self.max_retries:
                    retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                    _time.sleep(min(retry_after, 60))
                    continue
                if resp.status_code >= 500 and attempt < self.max_retries:
                    _time.sleep(min(2 ** attempt, 60))
                    continue
                return self._check(resp)
            except (requests.ConnectionError, requests.Timeout) as e:
                last_exc = e
                if attempt < self.max_retries:
                    _time.sleep(min(2 ** attempt, 60))
                    continue
                raise SurfAPIError(f"Connection failed after {self.max_retries + 1} attempts: {e}",
                                   status_code=0, error_code="connection_error")
        if last_exc:
            raise last_exc
        return {}

    def _check(self, resp: requests.Response) -> dict:
        if resp.status_code == 401:
            raise SurfAuthError("RTB authentication failed (401). Check your API key and rtb:* scopes.", status_code=401)
        if resp.status_code == 403:
            raise SurfScopeError("RTB forbidden (403). Your API key may lack the required rtb:* scope.", status_code=403)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "5")
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

    def bid(self, request: dict, sandbox: bool = False) -> dict:
        """Send an OpenRTB 2.5 bid request.

        Args:
            request: OpenRTB bid request dict. Must include 'id' and 'imp'.
            sandbox: If True, sets test=1 to get synthetic bids without real spend.

        Returns:
            OpenRTB bid response dict with seatbid array.
        """
        if sandbox:
            request = {**request, "test": 1}
        return self._request("POST", "/bid", json=request)

    def reports(self, days: int = 30, granularity: str = "day", app_id: int = None) -> dict:
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
        return self._request("GET", "/reports", params=params)

    def config(self, app_id: int = None) -> dict:
        """Get RTB configuration and tier info.

        Returns:
            Dict with 'config' and 'tiers' keys.
        """
        params = {}
        if app_id is not None:
            params["app_id"] = app_id
        return self._request("GET", "/config", params=params)

    def scopes(self) -> list:
        """List available RTB scopes."""
        return self._request("GET", "/scopes").get("scopes", [])

    def ads_txt(self, app_id: str = None) -> dict:
        """Get your personalized ads.txt entry for authorizing Surf as a seller.

        Add the returned `entries` to the ads.txt file at the root of each
        domain where you display Surf ads.

        Returns:
            Dict with 'seller_id', 'entries', 'sellers_json_url', 'instructions'.
        """
        params = {}
        if app_id is not None:
            params["app_id"] = app_id
        return self._request("GET", "/ads-txt", params=params)


class _DiagnosticsAPI:
    """Self-service diagnostics and confidential debug-bundle sharing.

    Lets your agent ask "what's wrong with my integration?" and, when handing a
    problem to Surf's support agent, share a redacted, short-lived snapshot of
    the diagnosis without exposing a credential.

    Example:
        diag = client.diagnostics.diagnose()        # this token's own app
        for f in diag["findings"]:
            print(f["severity"], f["title"], "->", f["recommendation"])

        bundle = client.diagnostics.create_bundle(ttl_minutes=15)
        print("Share with Surf support:", bundle["share_url"])
    """

    def __init__(self, client: SurfClient):
        self._c = client

    def diagnose(self, app_id: str = None) -> dict:
        """Structured diagnosis (findings + token health + usage + errors).

        With an app API key, omit `app_id` to diagnose that token's own app.
        With a developer session, pass the app's public id.
        """
        path = f"/applications/{quote(app_id, safe='')}/diagnose" if app_id else "/diagnose"
        return self._c._dp_get(path)

    def create_bundle(self, app_id: str = None, ttl_minutes: int = 15) -> dict:
        """Mint a redacted, expiring debug bundle. Returns share_token + share_url."""
        path = f"/applications/{quote(app_id, safe='')}/debug-bundle" if app_id else "/debug-bundle"
        return self._c._dp_post(path, json={"ttl_minutes": ttl_minutes})

    def get_bundle(self, token: str) -> dict:
        """Fetch a shared bundle by its share token (no auth required)."""
        return self._c._dp_get(f"/debug-bundle/{quote(token, safe='')}")

    def revoke_bundle(self, token: str) -> dict:
        """Revoke a bundle you minted before it expires."""
        return self._c._dp_delete(f"/debug-bundle/{quote(token, safe='')}")


def episode_url_sha1(episode_url: str) -> str:
    """SHA1 hex of a full episode audio URL.

    ``episode_url_hash`` is the episode's stable ID across the podcast
    intelligence endpoints (episode search results, guest appearances,
    mentions, and the sponsor/ads database).
    """
    import hashlib
    return hashlib.sha1(episode_url.encode("utf-8")).hexdigest()


def _clean(params: Optional[dict]) -> Optional[dict]:
    """Remove None values from params dict."""
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
