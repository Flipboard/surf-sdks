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
API_PREFIX = "/flipboard/v1"


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

        # Get posts from a feed
        posts = client.feeds.get_posts("surf/topic/technology", limit=20)

        # Search feeds
        results = client.search.feeds("artificial intelligence")

        # Natural language search
        results = client.search.ask("feeds about sustainable energy")

        # Generate a radio show
        station = client.audio.create_radio_station(feed_surf_id="surf/topic/technology")
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
            "User-Agent": "surf-api-python/0.1.0",
        })

        # Sub-clients
        self.feeds = _FeedsAPI(self)
        self.search = _SearchAPI(self)
        self.audio = _AudioAPI(self)
        self.account = _AccountAPI(self)
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

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._request("GET", path, params=_clean(params))

    def _post(self, path: str, json: Optional[dict] = None, **kwargs) -> dict:
        return self._request("POST", path, json=json, **kwargs)

    def _put(self, path: str, json: Optional[dict] = None) -> dict:
        return self._request("PUT", path, json=json)

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


class _FeedsAPI:
    """Feed operations (read:feeds scope)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def get(self, surf_id: str) -> dict:
        """Get feed metadata."""
        return self._c._get("/feed", {"surfId": surf_id})

    def get_public(self, surf_id: str) -> dict:
        """Get public feed metadata (no auth required)."""
        return self._c._get("/feed/public", {"surfId": surf_id})

    def get_multiple(self, surf_ids: list[str]) -> dict:
        """Get metadata for multiple feeds."""
        return self._c._get("/feed/multiple", {"surfIds": ",".join(surf_ids)})

    def get_posts(self, surf_id: str, limit: int = 20, cursor: str = None, services: str = None) -> dict:
        """Get posts from a feed."""
        return self._c._get("/feed/posts", {
            "surfId": surf_id, "limit": limit, "cursor": cursor, "services": services,
        })

    def get_post(self, surf_id: str) -> dict:
        """Get a single post by Surf ID."""
        return self._c._get("/feed/post/simple", {"surfId": surf_id})

    def get_home_timeline(self, limit: int = 20, cursor: str = None) -> dict:
        """Get the authenticated user's home timeline."""
        return self._c._get("/feed/home", {"limit": limit, "cursor": cursor})

    def get_trending(self, limit: int = 20) -> dict:
        """Get trending posts."""
        return self._c._get("/feed/trends/statuses", {"limit": limit})

    def get_top_posts(self, surf_id: str, limit: int = 20) -> dict:
        """Get top posts from a feed."""
        return self._c._get("/feed/posts/top", {"surfId": surf_id, "limit": limit})

    def get_topics(self) -> dict:
        """Get available topics."""
        return self._c._get("/feed/get_topics")

    def get_summary(self, surf_id: str) -> dict:
        """Get an AI-generated summary of a feed."""
        return self._c._get("/feed/summary", {"surfId": surf_id})

    def get_post_summary(self, surf_id: str) -> dict:
        """Get an AI-generated summary of a post/thread."""
        return self._c._get("/feed/post/summary", {"surfId": surf_id})

    def get_rss(self, surf_id: str) -> str:
        """Get RSS XML for a feed."""
        resp = self._c._session.get(
            self._c._url("/feed/posts/rss"),
            params={"surfId": surf_id},
            timeout=self._c.timeout,
        )
        self._c._check_errors(resp)
        return resp.text

    def preview_posts(self, operators: list[dict], limit: int = 20) -> dict:
        """Preview posts from a feed specification (before creating)."""
        return self._c._post("/feed/posts/specification", json={
            "operators": operators, "limit": limit,
        })

    def get_following(self, limit: int = 50) -> dict:
        """Get feeds the authenticated user follows."""
        return self._c._get("/feed/following", {"limit": limit})

    def get_recommended(self, surf_id: str = None, limit: int = 20) -> dict:
        """Get recommended feeds."""
        return self._c._get("/search/maestra/recommend", {"surfId": surf_id, "limit": limit})

    def get_similar(self, feed_id: str, limit: int = 20) -> dict:
        """Get feeds similar to the given feed."""
        return self._c._get("/search/maestra/feeds/similar", {"feedId": feed_id, "limit": limit})

    def get_personalized(self, limit: int = 20) -> dict:
        """Get personalized feed recommendations."""
        return self._c._get("/search/account/maestra/feeds/personalized", {"limit": limit})


class _SearchAPI:
    """Search operations (read:search scope)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def feeds(self, query: str, limit: int = 20, page_token: str = None) -> dict:
        """Search for feeds."""
        return self._c._get("/search/maestra/feeds", {
            "q": query, "limit": limit, "pageToken": page_token,
        })

    def posts(self, query: str, limit: int = 20) -> dict:
        """Search for posts/statuses."""
        return self._c._get("/search/posts", {"q": query, "limit": limit})

    def accounts(self, query: str, limit: int = 20) -> dict:
        """Search for accounts."""
        return self._c._get("/search/accounts", {"q": query, "limit": limit})

    def bluesky_actors(self, query: str, limit: int = 20) -> dict:
        """Search for Bluesky users."""
        return self._c._get("/search/bluesky/actors", {"q": query, "limit": limit})

    def rss(self, query: str) -> dict:
        """Search for RSS feeds by URL or keyword."""
        return self._c._get("/search/rss", {"q": query})

    def podcasts(self, query: str, limit: int = 20) -> dict:
        """Search for podcasts."""
        return self._c._get("/search/podcasts", {"q": query, "limit": limit})

    def ask(self, query: str, k: int = 10, schema_type: str = None, feed_id: str = None) -> dict:
        """Natural language search powered by NLWeb."""
        return self._c._get("/search/ask", {
            "query": query, "k": k, "schema_type": schema_type, "feed_id": feed_id,
        })


class _AudioAPI:
    """Audio operations (read:audio / write:audio scopes)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def list_stations(self) -> dict:
        """List available radio stations."""
        return self._c._get("/audio/radio/stations")

    def get_station(self, station_id: str) -> dict:
        """Get a radio station."""
        return self._c._get(f"/audio/radio/station/{station_id}")

    def create_station(self, feed_surf_id: str, title: str = None) -> dict:
        """Create a radio station from a feed (write:audio)."""
        body = {"feedSurfId": feed_surf_id}
        if title:
            body["title"] = title
        return self._c._post("/audio/radio/station", json=body)

    def generate_program(self, station_id: str) -> dict:
        """Generate a new radio program for a station (write:audio)."""
        return self._c._post(f"/audio/radio/station/{station_id}/program")

    def get_manifest(self, station_id: str, program_id: str = None) -> dict:
        """Get the audio manifest (playlist) for a station."""
        return self._c._get(f"/audio/radio/station/{station_id}/manifest", {
            "programId": program_id,
        })

    def get_briefing(self, briefing_id: str = None) -> dict:
        """Get a daily briefing."""
        if briefing_id:
            return self._c._get(f"/audio/briefing/{briefing_id}")
        return self._c._get("/audio/briefing/latest")

    def generate_briefing(self) -> dict:
        """Generate a new daily briefing (write:audio)."""
        return self._c._post("/audio/briefing/generate")

    def get_briefing_segments(self, briefing_id: str) -> dict:
        """Get segments/chapters for a briefing."""
        return self._c._get(f"/audio/briefing/{briefing_id}/segments")

    def get_transcript(self, post_surf_id: str) -> dict:
        """Get the transcript for a post's audio."""
        return self._c._get("/audio/transcript", {"surfId": post_surf_id})

    def get_quiz(self) -> dict:
        """Get the daily quiz."""
        return self._c._get("/audio/quiz/daily")


class _AccountAPI:
    """Account operations (read:account / write:account scopes)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def get(self) -> dict:
        """Get the authenticated user's account info."""
        return self._c._get("/account")

    def lookup(self, username: str = None, account_id: str = None) -> dict:
        """Look up an account by username or ID."""
        return self._c._get("/feed/lookup", {"username": username, "id": account_id})

    def get_activity(self, limit: int = 20) -> dict:
        """Get account activity."""
        return self._c._get("/account/activity", {"limit": limit})


class _NotificationsAPI:
    """Notification operations (read:notifications scope)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def list(self, limit: int = 30, cursor: str = None) -> dict:
        """Get notifications."""
        return self._c._get("/notifications", {"limit": limit, "cursor": cursor})

    def get_badge_count(self) -> dict:
        """Get unread notification count."""
        return self._c._get("/notifications/badge")

    def reset_badge(self) -> dict:
        """Reset the unread notification count."""
        return self._c._post("/notifications/badge/reset")


class _PreferencesAPI:
    """Preference operations (read:preferences / write:preferences scopes)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def get(self) -> dict:
        """Get user preferences."""
        return self._c._get("/preferences")

    def update(self, preferences: dict) -> dict:
        """Update user preferences (write:preferences)."""
        return self._c._put("/preferences", json=preferences)


class _CustomFeedsAPI:
    """Custom feed operations (write:feeds scope)."""

    def __init__(self, client: SurfClient):
        self._c = client

    def list(self, limit: int = 50) -> dict:
        """List custom feeds owned by the authenticated user."""
        return self._c._get("/builder/feeds", {"limit": limit})

    def get(self, feed_id: str) -> dict:
        """Get a custom feed by ID."""
        return self._c._get(f"/builder/feed/{feed_id}")

    def create(self, title: str, description: str = None, operators: list[dict] = None) -> dict:
        """Create a new custom feed."""
        body = {"title": title}
        if description:
            body["description"] = description
        if operators:
            body["operators"] = operators
        return self._c._post("/builder/feed", json=body)

    def update(self, feed_id: str, **kwargs) -> dict:
        """Update a custom feed (title, description, operators, etc.)."""
        return self._c._put(f"/builder/feed/{feed_id}", json=kwargs)

    def delete(self, feed_id: str) -> dict:
        """Delete a custom feed."""
        return self._c._delete(f"/builder/feed/{feed_id}")

    def clone(self, feed_id: str, title: str = None) -> dict:
        """Clone an existing custom feed."""
        body = {"feedId": feed_id}
        if title:
            body["title"] = title
        return self._c._post("/builder/feed/clone", json=body)

    def publish(self, feed_id: str) -> dict:
        """Publish a custom feed (makes it publicly discoverable)."""
        return self._c._post(f"/builder/feed/{feed_id}/publish")

    def add_operator(self, feed_id: str, operator: dict) -> dict:
        """Add an operator (source) to a custom feed."""
        return self._c._post(f"/builder/feed/{feed_id}/operator", json=operator)

    def update_operator(self, feed_id: str, operator_id: str, operator: dict) -> dict:
        """Update an operator in a custom feed."""
        return self._c._put(f"/builder/feed/{feed_id}/operator/{operator_id}", json=operator)

    def remove_operator(self, feed_id: str, operator_id: str) -> dict:
        """Remove an operator from a custom feed."""
        return self._c._delete(f"/builder/feed/{feed_id}/operator/{operator_id}")


class _MediaAPI:
    """Media operations."""

    def __init__(self, client: SurfClient):
        self._c = client

    def upload(self, file_path: str, content_type: str = "image/jpeg") -> dict:
        """Upload a media file (image)."""
        with open(file_path, "rb") as f:
            resp = self._c._session.post(
                self._c._url("/media"),
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
