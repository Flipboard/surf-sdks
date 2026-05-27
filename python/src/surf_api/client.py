"""Surf API client."""

from __future__ import annotations

from typing import Any, Iterator, Optional

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
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.rate_limit: Optional[RateLimitInfo] = None

        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "surf-api-python/0.2.0",
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

    def _url(self, path: str) -> str:
        return f"{self.base_url}{API_PREFIX}{path}"

    def _request(self, method: str, path: str, **kwargs) -> dict:
        kwargs.setdefault("timeout", self.timeout)
        resp = self._session.request(method, self._url(path), **kwargs)
        self.rate_limit = RateLimitInfo(resp.headers)
        self._check_errors(resp)
        if resp.status_code == 204:
            return {}
        return resp.json()

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

    def _paginate(self, path: str, key: str, params: dict, limit: Optional[int] = None) -> Iterator[dict]:
        """Auto-paginate through results."""
        params = dict(params or {})
        fetched = 0
        while True:
            data = self._get(path, params)
            items = data.get(key, [])
            if not items:
                break
            for item in items:
                yield item
                fetched += 1
                if limit and fetched >= limit:
                    return
            cursor = data.get("cursor") or data.get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor


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
                  sort: str = None, services: str = None) -> dict:
        """Get posts from a feed."""
        return self._c._get("/feed/posts", {
            "surf_id": surf_id, "limit": limit, "cursor": cursor,
            "sort": sort, "services": services,
        })

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
                    spoiler_text: str = None, language: str = None) -> dict:
        """Create a new post (write:statuses). Use OAuth token for user-delegated posting."""
        body = {"status": status, "visibility": visibility}
        if in_reply_to_id:
            body["in_reply_to_id"] = in_reply_to_id
        if sensitive:
            body["sensitive"] = True
        if spoiler_text:
            body["spoiler_text"] = spoiler_text
        if language:
            body["language"] = language
        return self._c._post("/statuses", json=body)

    def favourite(self, post_id: str) -> dict:
        """Favorite a post (write:statuses)."""
        return self._c._post(f"/statuses/{post_id}/favourite")

    def unfavourite(self, post_id: str) -> dict:
        """Unfavorite a post (write:statuses)."""
        return self._c._post(f"/statuses/{post_id}/unfavourite")

    def boost(self, post_id: str) -> dict:
        """Boost/reblog a post (write:statuses)."""
        return self._c._post(f"/statuses/{post_id}/reblog")

    def unboost(self, post_id: str) -> dict:
        """Unboost a post (write:statuses)."""
        return self._c._post(f"/statuses/{post_id}/unreblog")

    def bookmark(self, post_id: str) -> dict:
        """Bookmark a post (write:statuses)."""
        return self._c._post(f"/statuses/{post_id}/bookmark")

    def delete_post(self, post_id: str) -> dict:
        """Delete own post (write:statuses)."""
        return self._c._delete(f"/statuses/{post_id}")


# ==========================================================================
# Search
# ==========================================================================

class _SearchAPI:
    """Search operations (read:search scope).

    The consolidated /search endpoint supports type=feeds|posts|accounts|podcasts|rss.
    """

    def __init__(self, client: SurfClient):
        self._c = client

    def search(self, query: str, type: str = "feeds", limit: int = 20) -> dict:
        """Unified search. type: feeds, posts, accounts, podcasts, rss."""
        return self._c._get("/search", {"q": query, "type": type, "limit": limit})

    def feeds(self, query: str, limit: int = 20) -> dict:
        """Search for feeds."""
        return self.search(query, type="feeds", limit=limit)

    def posts(self, query: str, limit: int = 20) -> dict:
        """Search for posts."""
        return self.search(query, type="posts", limit=limit)

    def accounts(self, query: str, limit: int = 20) -> dict:
        """Search for accounts."""
        return self.search(query, type="accounts", limit=limit)

    def podcasts(self, query: str, limit: int = 20) -> dict:
        """Search for podcasts."""
        return self.search(query, type="podcasts", limit=limit)

    def discover(self, type: str = "recommended", surf_id: str = None, limit: int = 20) -> dict:
        """Discover feeds. type: recommended, similar, interests."""
        return self._c._get("/search/discover", {
            "type": type, "surf_id": surf_id, "limit": limit,
        })


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

    def create(self, title: str, description: str = None, operators: list = None) -> dict:
        """Create a new custom feed."""
        body = {"title": title}
        if description:
            body["description"] = description
        if operators:
            body["operators"] = operators
        return self._c._post("/custom", json=body)

    def update(self, feed_id: str, **kwargs) -> dict:
        """Update a custom feed."""
        return self._c._put(f"/custom/{feed_id}", json=kwargs)

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
        return self._c._post(f"/custom/{feed_id}/operators", json=operator)

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


def _clean(params: Optional[dict]) -> Optional[dict]:
    """Remove None values from params dict."""
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}
