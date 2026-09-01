"""Unit tests for the podcast popularity audio endpoints — no live API.

Verifies the API contract: paths and query params for the popular-shows and
hot-episodes charts (including the camelCase ``ingestedOnly`` wire param and
its boolean serialization); None params dropped; and the typed model parsers.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import patch, MagicMock

import pytest

from surf_api import SurfClient
from surf_api.models import PopularEpisode, PopularShow

BASE = "https://api.surf.social/v1"


def _mk_resp(status_code=200, json_body=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.headers = headers or {}
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def _capture(client, json_body=None):
    """Patch the client's session and return the mock so we can inspect calls."""
    return patch.object(client._session, "request", return_value=_mk_resp(json_body=json_body))


def _client():
    return SurfClient(api_key="k")


SHOW_ROW = {
    "rank": 1,
    "score": 97.4,
    "flyf_id": "d7e340ff6462708b5519d65d3faab82ecb6c4c37",
    "ingested": True,
    "feed_url": "https://feeds.example.com/acquired.rss",
    "title": "Acquired",
    "artwork_url": "https://cdn.example.com/acquired.jpg",
    "itunes_id": 1050462261,
    "podcastindex_id": 217134,
    "apple_rank": 3,
    "pi_trend_rank": 7,
    "engagement_7d": 4211,
    "created_at": "2026-08-31T06:00:00Z",
}

EPISODE_ROW = {
    "rank": 1,
    "score": 88.2,
    "episode_url_hash": "a" * 40,
    "episode_url": "https://cdn.example.com/podcasts/ep-142.mp3",
    "flyf_id": "d7e340ff6462708b5519d65d3faab82ecb6c4c37",
    "title": "Nvidia part III",
    "show_title": "Acquired",
    "artwork_url": "https://cdn.example.com/acquired.jpg",
    "engagement_sum": 913,
    "post_count": 57,
    "created_at": "2026-08-31T06:00:00Z",
}


# ==========================================================================
# Popular shows
# ==========================================================================

class TestGetPopularShows:
    def test_path_and_default_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_popular_shows()
        method, url = m.call_args.args[0], m.call_args.args[1]
        assert method == "GET"
        assert url == f"{BASE}/audio/popular/shows"
        # date=None dropped; ingestedOnly serialized lowercase for Spring
        assert m.call_args.kwargs["params"] == {
            "region": "us", "category": "all", "limit": 50,
            "ingestedOnly": "true",
        }

    def test_all_params_passed_through(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_popular_shows(region="gb", category="technology",
                                      limit=10, ingested_only=False,
                                      date="2026-08-30")
        assert m.call_args.kwargs["params"] == {
            "region": "gb", "category": "technology", "limit": 10,
            "ingestedOnly": "false", "date": "2026-08-30",
        }

    def test_envelope_passthrough(self):
        c = _client()
        body = {"ok": True, "region": "us", "category": "all",
                "snapshot_date": "2026-08-31", "ingested_only": True,
                "limit": 50, "shows": [SHOW_ROW], "total": 1}
        with _capture(c, json_body=body):
            out = c.audio.get_popular_shows()
        assert out["snapshot_date"] == "2026-08-31"
        assert out["shows"][0]["apple_rank"] == 3


# ==========================================================================
# Popular episodes
# ==========================================================================

class TestGetPopularEpisodes:
    def test_path_and_default_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_popular_episodes()
        method, url = m.call_args.args[0], m.call_args.args[1]
        assert method == "GET"
        assert url == f"{BASE}/audio/popular/episodes"
        assert m.call_args.kwargs["params"] == {"limit": 50}

    def test_limit_and_date_passed_through(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_popular_episodes(limit=5, date="2026-08-30")
        assert m.call_args.kwargs["params"] == {"limit": 5, "date": "2026-08-30"}


# ==========================================================================
# Async client parity
# ==========================================================================

class TestAsyncPopularity:
    @staticmethod
    def _async_client_and_mock(json_body=None):
        pytest.importorskip("httpx")
        import asyncio
        from unittest.mock import AsyncMock
        from surf_api.async_client import AsyncSurfClient

        c = AsyncSurfClient(api_key="k")
        m = AsyncMock(return_value=_mk_resp(json_body=json_body))
        c._client.request = m
        return c, m, asyncio

    def test_get_popular_shows_route_and_params(self):
        c, m, asyncio = self._async_client_and_mock()
        asyncio.run(c.audio.get_popular_shows(region="gb", category="technology",
                                              limit=10, ingested_only=False,
                                              date="2026-08-30"))
        method, path = m.call_args.args[0], m.call_args.args[1]
        assert method == "GET"
        assert path == "/audio/popular/shows"
        assert m.call_args.kwargs["params"] == {
            "region": "gb", "category": "technology", "limit": 10,
            "ingestedOnly": "false", "date": "2026-08-30",
        }
        asyncio.run(c.close())

    def test_get_popular_shows_defaults_drop_date(self):
        c, m, asyncio = self._async_client_and_mock()
        asyncio.run(c.audio.get_popular_shows())
        assert m.call_args.args[1] == "/audio/popular/shows"
        assert m.call_args.kwargs["params"] == {
            "region": "us", "category": "all", "limit": 50,
            "ingestedOnly": "true",
        }
        asyncio.run(c.close())

    def test_get_popular_episodes_route_and_params(self):
        c, m, asyncio = self._async_client_and_mock()
        asyncio.run(c.audio.get_popular_episodes(limit=3, date="2026-08-30"))
        assert m.call_args.args[1] == "/audio/popular/episodes"
        assert m.call_args.kwargs["params"] == {"limit": 3, "date": "2026-08-30"}
        asyncio.run(c.close())


# ==========================================================================
# Typed models
# ==========================================================================

class TestPopularShowModel:
    def test_from_dict(self):
        s = PopularShow.from_dict(SHOW_ROW)
        assert s.rank == 1
        assert s.score == 97.4
        assert s.flyf_id == SHOW_ROW["flyf_id"]
        assert s.ingested is True
        assert s.feed_url == SHOW_ROW["feed_url"]
        assert s.title == "Acquired"
        assert s.itunes_id == 1050462261
        assert s.podcastindex_id == 217134
        assert s.apple_rank == 3
        assert s.pi_trend_rank == 7
        assert s.engagement_7d == 4211
        assert s.created_at == "2026-08-31T06:00:00Z"

    def test_from_dict_minimal_and_none(self):
        s = PopularShow.from_dict({"rank": 2, "score": 1.0})
        assert s.rank == 2
        assert s.ingested is False
        assert s.apple_rank is None
        assert PopularShow.from_dict(None) is None
        assert PopularShow.from_dict({}) is None

    def test_from_list_accepts_response_dict(self):
        shows = PopularShow.from_list({"ok": True, "shows": [SHOW_ROW, SHOW_ROW]})
        assert len(shows) == 2
        assert shows[0].title == "Acquired"

    def test_from_list_accepts_bare_list_and_garbage(self):
        assert len(PopularShow.from_list([SHOW_ROW])) == 1
        assert PopularShow.from_list("nope") == []
        assert PopularShow.from_list({"ok": True}) == []


class TestPopularEpisodeModel:
    def test_from_dict(self):
        e = PopularEpisode.from_dict(EPISODE_ROW)
        assert e.rank == 1
        assert e.score == 88.2
        assert e.episode_url_hash == "a" * 40
        assert e.episode_url.endswith("ep-142.mp3")
        assert e.flyf_id == EPISODE_ROW["flyf_id"]
        assert e.title == "Nvidia part III"
        assert e.show_title == "Acquired"
        assert e.engagement_sum == 913
        assert e.post_count == 57

    def test_from_dict_none(self):
        assert PopularEpisode.from_dict(None) is None
        assert PopularEpisode.from_dict({}) is None

    def test_from_list_accepts_response_dict(self):
        eps = PopularEpisode.from_list({"ok": True, "episodes": [EPISODE_ROW]})
        assert len(eps) == 1
        assert eps[0].show_title == "Acquired"

    def test_from_list_accepts_bare_list(self):
        assert len(PopularEpisode.from_list([EPISODE_ROW, EPISODE_ROW])) == 2
