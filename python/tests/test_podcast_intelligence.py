"""Unit tests for the podcast intelligence audio endpoints — no live API.

Verifies the API contract: paths and query params for episode/guest search,
mentions, sponsors, and show notes; None params dropped; the sponsors
company-or-episode requirement; `episode_url` convenience hashing; and the
typed model parsers.
"""

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import patch, MagicMock

import pytest

from surf_api import SurfClient, episode_url_sha1
from surf_api.models import (
    PodcastEpisodeSearchResult,
    PodcastGuest,
    PodcastMention,
    PodcastSponsorAd,
)

BASE = "https://api.surf.social/v1"
EPISODE_URL = "https://cdn.example.com/podcasts/ep-142.mp3"
EPISODE_URL_HASH = hashlib.sha1(EPISODE_URL.encode("utf-8")).hexdigest()
FLYF_ID = "d7e340ff6462708b5519d65d3faab82ecb6c4c37"


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


# ==========================================================================
# Episode search
# ==========================================================================

class TestSearchPodcastEpisodes:
    def test_path_and_default_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.search_podcast_episodes("ai agents")
        method, url = m.call_args.args[0], m.call_args.args[1]
        assert method == "GET"
        assert url == f"{BASE}/audio/episodes/search"
        assert m.call_args.kwargs["params"] == {"q": "ai agents", "limit": 20}

    def test_flyf_id_and_limit_passed_through(self):
        c = _client()
        with _capture(c) as m:
            c.audio.search_podcast_episodes("ai", flyf_id=FLYF_ID, limit=5)
        assert m.call_args.kwargs["params"] == {"q": "ai", "flyf_id": FLYF_ID, "limit": 5}


# ==========================================================================
# Guest search
# ==========================================================================

class TestSearchPodcastGuests:
    def test_path_and_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.search_podcast_guests("Sam Altman", limit=3)
        assert m.call_args.args[1] == f"{BASE}/audio/guests/search"
        assert m.call_args.kwargs["params"] == {"q": "Sam Altman", "limit": 3}


# ==========================================================================
# Mentions
# ==========================================================================

class TestGetPodcastMentions:
    def test_path_and_default_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_podcast_mentions("Anthropic")
        assert m.call_args.args[1] == f"{BASE}/audio/mentions"
        assert m.call_args.kwargs["params"] == {
            "entity": "Anthropic", "limit": 20, "offset": 0,
        }

    def test_all_filters_passed_through(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_podcast_mentions("Anthropic", entity_type="organization",
                                         flyf_id=FLYF_ID, limit=50, offset=100)
        assert m.call_args.kwargs["params"] == {
            "entity": "Anthropic", "entity_type": "organization",
            "flyf_id": FLYF_ID, "limit": 50, "offset": 100,
        }


# ==========================================================================
# Sponsors
# ==========================================================================

class TestGetPodcastSponsors:
    def test_by_company(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_podcast_sponsors(company="Squarespace")
        assert m.call_args.args[1] == f"{BASE}/audio/sponsors"
        assert m.call_args.kwargs["params"] == {
            "company": "Squarespace", "limit": 20, "offset": 0,
        }

    def test_by_episode_url_hash(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_podcast_sponsors(episode_url_hash=EPISODE_URL_HASH)
        assert m.call_args.kwargs["params"] == {
            "episode_url_hash": EPISODE_URL_HASH, "limit": 20, "offset": 0,
        }

    def test_episode_url_is_hashed(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_podcast_sponsors(episode_url=EPISODE_URL)
        params = m.call_args.kwargs["params"]
        assert params["episode_url_hash"] == EPISODE_URL_HASH
        assert "episode_url" not in params

    def test_explicit_hash_wins_over_episode_url(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_podcast_sponsors(episode_url_hash="a" * 40,
                                         episode_url=EPISODE_URL)
        assert m.call_args.kwargs["params"]["episode_url_hash"] == "a" * 40

    def test_requires_company_or_episode(self):
        c = _client()
        with pytest.raises(ValueError):
            c.audio.get_podcast_sponsors()

    def test_company_and_episode_combine(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_podcast_sponsors(company="Squarespace",
                                         episode_url_hash=EPISODE_URL_HASH,
                                         flyf_id=FLYF_ID)
        assert m.call_args.kwargs["params"] == {
            "company": "Squarespace", "episode_url_hash": EPISODE_URL_HASH,
            "flyf_id": FLYF_ID, "limit": 20, "offset": 0,
        }


# ==========================================================================
# Show notes
# ==========================================================================

class TestGetShowNotes:
    def test_path_and_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_show_notes(EPISODE_URL)
        assert m.call_args.args[1] == f"{BASE}/audio/transcripts/show-notes"
        assert m.call_args.kwargs["params"] == {"episode_url": EPISODE_URL}

    def test_language_passed_through(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_show_notes(EPISODE_URL, language="es")
        assert m.call_args.kwargs["params"] == {
            "episode_url": EPISODE_URL, "language": "es",
        }


# ==========================================================================
# Hash helper
# ==========================================================================

class TestEpisodeUrlSha1:
    def test_known_vector(self):
        assert episode_url_sha1(EPISODE_URL) == EPISODE_URL_HASH
        assert len(episode_url_sha1(EPISODE_URL)) == 40


# ==========================================================================
# Typed models
# ==========================================================================

class TestModels:
    def test_episode_result_from_list(self):
        resp = {"ok": True, "query": "ai", "total": 1, "results": [{
            "episode_url": EPISODE_URL, "episode_url_hash": EPISODE_URL_HASH,
            "flyf_id": FLYF_ID, "podcast_name": "The AI Weekly Show",
            "episode_title": "Ep 142", "score": 0.83,
            "chunk_start_seconds": 512.4, "chunk_end_seconds": 640.1,
            "preview": "…agents went from demos to production…",
        }]}
        results = PodcastEpisodeSearchResult.from_list(resp)
        assert len(results) == 1
        r = results[0]
        assert r.episode_url_hash == EPISODE_URL_HASH
        assert r.score == 0.83
        assert r.chunk_start_seconds == 512.4

    def test_guest_from_list_with_appearances(self):
        resp = {"ok": True, "guests": [{
            "name": "Sam Altman", "title": "CEO", "organization": "OpenAI",
            "bluesky_handle": None, "mastodon_handle": None,
            "appearances": [{
                "flyf_id": FLYF_ID, "podcast_name": "The AI Weekly Show",
                "episode_url": EPISODE_URL, "episode_url_hash": EPISODE_URL_HASH,
                "role": "guest", "confidence": 0.94,
                "speaking_time_seconds": 1820.5,
                "detected_at": "2026-08-20T04:12:00Z",
            }],
        }]}
        guests = PodcastGuest.from_list(resp)
        assert guests[0].name == "Sam Altman"
        assert guests[0].appearances[0].role == "guest"
        assert guests[0].appearances[0].speaking_time_seconds == 1820.5

    def test_mention_from_list(self):
        resp = {"mentions": [{
            "episode_url": EPISODE_URL, "episode_url_hash": EPISODE_URL_HASH,
            "entity": "Anthropic", "entity_type": "organization",
            "mention_count": 7, "first_start_seconds": 312.6,
            "timestamps": [{"start": 312.6, "end": 314.1}],
        }]}
        mentions = PodcastMention.from_list(resp)
        assert mentions[0].mention_count == 7
        assert mentions[0].timestamps == [{"start": 312.6, "end": 314.1}]

    def test_sponsor_from_list(self):
        resp = {"sponsors": [{
            "episode_url": EPISODE_URL, "episode_url_hash": EPISODE_URL_HASH,
            "company": "Squarespace", "product": "Website builder",
            "category": "technology", "ad_format": "host_read",
            "promo_code": "AIWEEKLY", "start_seconds": 903.2,
            "end_seconds": 967.8, "duration_seconds": 64.6,
            "confidence": 0.91, "ad_text_preview": "This episode is brought to you by…",
            "model_version": "sponsor-v1", "created_at": "2026-08-20T04:12:00Z",
        }]}
        ads = PodcastSponsorAd.from_list(resp)
        assert ads[0].company == "Squarespace"
        assert ads[0].promo_code == "AIWEEKLY"
        assert ads[0].duration_seconds == 64.6

    def test_from_dict_none_returns_none(self):
        assert PodcastEpisodeSearchResult.from_dict(None) is None
        assert PodcastGuest.from_dict({}) is None
        assert PodcastMention.from_list([]) == []
        assert PodcastSponsorAd.from_list({"no_key": []}) == []


# ==========================================================================
# Phase 4 — fact checks
# ==========================================================================

class TestGetFactChecks:
    def test_path_and_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_fact_checks(EPISODE_URL)
        method, url = m.call_args.args[0], m.call_args.args[1]
        assert method == "GET"
        assert url == f"{BASE}/audio/fact-checks"
        assert m.call_args.kwargs["params"] == {"episode_url": EPISODE_URL}


# ==========================================================================
# Phase 4 — translations
# ==========================================================================

class TestGetTranslation:
    def test_path_and_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_translation(EPISODE_URL, "es")
        assert m.call_args.args[1] == f"{BASE}/audio/translations"
        assert m.call_args.kwargs["params"] == {
            "episode_url": EPISODE_URL, "language": "es",
        }

    def test_regional_language_code_passed_verbatim(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_translation(EPISODE_URL, "pt-BR")
        assert m.call_args.kwargs["params"]["language"] == "pt-BR"


# ==========================================================================
# Phase 4 — catch-up
# ==========================================================================

class TestGetCatchUp:
    def test_path_and_params(self):
        c = _client()
        with _capture(c) as m:
            c.audio.get_catch_up(EPISODE_URL, 1830.5)
        assert m.call_args.args[1] == f"{BASE}/audio/catch-up"
        assert m.call_args.kwargs["params"] == {
            "episode_url": EPISODE_URL, "timestamp": 1830.5,
        }

    def test_zero_timestamp_is_sent(self):
        # 0 is a valid position and must not be dropped by param cleaning
        c = _client()
        with _capture(c) as m:
            c.audio.get_catch_up(EPISODE_URL, 0)
        assert m.call_args.kwargs["params"]["timestamp"] == 0


# ==========================================================================
# Phase 4 — skip-to-topic
# ==========================================================================

class TestSkipToTopic:
    def test_path_and_default_limit(self):
        c = _client()
        with _capture(c) as m:
            c.audio.skip_to_topic(EPISODE_URL, "the housing market")
        assert m.call_args.args[1] == f"{BASE}/audio/skip-to-topic"
        assert m.call_args.kwargs["params"] == {
            "episode_url": EPISODE_URL, "topic": "the housing market", "limit": 5,
        }

    def test_limit_passed_through(self):
        c = _client()
        with _capture(c) as m:
            c.audio.skip_to_topic(EPISODE_URL, "evals", limit=20)
        assert m.call_args.kwargs["params"]["limit"] == 20


# ==========================================================================
# Phase 4 — typed models
# ==========================================================================

class TestPhase4Models:
    def test_fact_check_from_list(self):
        from surf_api.models import PodcastFactCheck
        resp = {"ok": True, "episode_url": EPISODE_URL, "total": 1,
                "summary": {"verified": 1}, "fact_checks": [{
                    "claim_index": 0,
                    "claim_text": "US inflation fell below 3 percent in 2025.",
                    "claim_type": "statistic",
                    "timestamp_seconds": 512.4,
                    "verdict": "verified",
                    "confidence": 0.92,
                    "explanation": "BLS CPI data confirms it.",
                    "sources": [{"title": "CPI Summary", "url": "https://bls.gov"}],
                    "search_queries": ["us inflation 2025"],
                }]}
        claims = PodcastFactCheck.from_list(resp)
        assert len(claims) == 1
        c = claims[0]
        assert c.verdict == "verified"
        assert c.confidence == 0.92
        assert c.timestamp_seconds == 512.4
        assert c.sources[0]["url"] == "https://bls.gov"
        assert c.search_queries == ["us inflation 2025"]

    def test_translation_from_dict_accepts_full_response(self):
        from surf_api.models import PodcastTranslation
        resp = {"ok": True, "episode_url": EPISODE_URL, "language": "es",
                "translation": {
                    "source_language": "en", "target_language": "es",
                    "translated_transcript": "Bienvenidos…",
                    "translated_segments": [{"start": 0.0, "end": 4.2,
                                             "text": "Bienvenidos…"}],
                    "audio_url": "https://example.com/es.mp3",
                    "audio_duration_seconds": 3712.5,
                    "tts_voice": "es-ES-ElviraNeural",
                    "word_count": 9421,
                    "original_duration_seconds": 3650.0,
                }}
        t = PodcastTranslation.from_dict(resp)
        assert t.target_language == "es"
        assert t.translated_transcript == "Bienvenidos…"
        assert t.word_count == 9421
        # A bare translation object parses the same way
        t2 = PodcastTranslation.from_dict(resp["translation"])
        assert t2 == t
        # The 404 shape (translation: null) parses to None
        assert PodcastTranslation.from_dict({"translation": None}) is None

    def test_topic_match_from_list(self):
        from surf_api.models import PodcastTopicMatch
        resp = {"ok": True, "topic": "housing", "total": 1, "matches": [{
            "start_seconds": 2105.3, "end_seconds": 2189.9,
            "text_preview": "…housing prices finally cooled…", "score": 0.78,
        }]}
        matches = PodcastTopicMatch.from_list(resp)
        assert matches[0].start_seconds == 2105.3
        assert matches[0].score == 0.78

    def test_phase4_from_dict_none_returns_none(self):
        from surf_api.models import (
            PodcastFactCheck, PodcastTranslation, PodcastTopicMatch,
        )
        assert PodcastFactCheck.from_dict(None) is None
        assert PodcastTranslation.from_dict({}) is None
        assert PodcastTopicMatch.from_list([]) == []
        assert PodcastFactCheck.from_list({"no_key": []}) == []
