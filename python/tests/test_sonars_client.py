"""Unit tests for the sonars namespace — no live API required.

Verifies the SDK matches the fldaily /sonars contract: method, path, query
params (with None dropped), JSON bodies (incl. the explicit-null daily_cap on
PATCH), the ``before`` cursor walk, and 204 -> {} on delete.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import patch, MagicMock

from surf_api import SurfClient, Sonar, SonarMatch, SonarPreview

BASE = "https://api.surf.social/v1"
SPEC = {"subject": {"hashtags": ["#opensearch"]}, "surfaces": ["bluesky", "mastodon"]}


def _mk_resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.headers = {}
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def _capture(client, json_body=None, status_code=200):
    return patch.object(client._session, "request", return_value=_mk_resp(status_code, json_body))


def test_create_sends_name_spec_and_only_the_delivery_fields_given():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.sonars.create("OpenSearch chatter", SPEC)
    assert m.call_args.args[:2] == ("POST", f"{BASE}/sonars")
    assert m.call_args.kwargs["json"] == {"name": "OpenSearch chatter", "spec": SPEC}

    with _capture(c) as m:
        c.sonars.create("n", SPEC, enabled=False, cadence="instant", channels=[{"type": "push"}], daily_cap=20)
    assert m.call_args.kwargs["json"] == {
        "name": "n", "spec": SPEC, "enabled": False, "cadence": "instant",
        "channels": [{"type": "push"}], "daily_cap": 20,
    }


def test_list_get_delete_paths_and_escaping():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.sonars.list()
    assert m.call_args.args[:2] == ("GET", f"{BASE}/sonars")
    with _capture(c) as m:
        c.sonars.get("01j0ksyw6tgwfs0zmhhbc42kwa")
    assert m.call_args.args[:2] == ("GET", f"{BASE}/sonars/01j0ksyw6tgwfs0zmhhbc42kwa")
    with _capture(c) as m:
        c.sonars.get("odd/id")
    assert m.call_args.args[1] == f"{BASE}/sonars/odd%2Fid"
    with _capture(c, status_code=204) as m:
        assert c.sonars.delete("abc") == {}
    assert m.call_args.args[:2] == ("DELETE", f"{BASE}/sonars/abc")


def test_update_is_a_patch_of_only_the_given_fields_and_can_clear_daily_cap():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.sonars.update("abc", name="renamed")
    assert m.call_args.args[:2] == ("PATCH", f"{BASE}/sonars/abc")
    assert m.call_args.kwargs["json"] == {"name": "renamed"}
    # explicit None is sent as null (clear the cap); an omitted field is not sent at all
    with _capture(c) as m:
        c.sonars.update("abc", daily_cap=None, enabled=False)
    assert m.call_args.kwargs["json"] == {"daily_cap": None, "enabled": False}


def test_matches_drops_absent_params_and_passes_the_cursor():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.sonars.matches("abc")
    assert m.call_args.args[:2] == ("GET", f"{BASE}/sonars/abc/matches")
    assert m.call_args.kwargs["params"] == {}
    with _capture(c) as m:
        c.sonars.matches("abc", before=41, limit=10)
    assert m.call_args.kwargs["params"] == {"before": 41, "limit": 10}


def test_iter_matches_follows_next_before_until_it_is_null():
    c = SurfClient(api_key="k")
    pages = [
        _mk_resp(200, {"matches": [{"id": 3, "post_id": "p3"}, {"id": 2, "post_id": "p2"}], "next_before": 2}),
        _mk_resp(200, {"matches": [{"id": 1, "post_id": "p1"}], "next_before": None}),
    ]
    with patch.object(c._session, "request", side_effect=pages) as m:
        got = [x["post_id"] for x in c.sonars.iter_matches("abc")]
    assert got == ["p3", "p2", "p1"]
    assert m.call_count == 2
    assert m.call_args_list[1].kwargs["params"] == {"before": 2}

    # a limit stops early and sizes the page request
    with patch.object(c._session, "request", return_value=pages[0]) as m:
        got = [x["post_id"] for x in c.sonars.iter_matches("abc", limit=1)]
    assert got == ["p3"]
    assert m.call_args.kwargs["params"] == {"limit": 1}


def test_preview_posts_the_spec_with_days_as_a_query_param():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.sonars.preview(SPEC)
    assert m.call_args.args[:2] == ("POST", f"{BASE}/sonars/preview")
    assert m.call_args.kwargs["json"] == SPEC
    assert m.call_args.kwargs["params"] == {}
    with _capture(c) as m:
        c.sonars.preview(SPEC, days=7)
    assert m.call_args.kwargs["params"] == {"days": 7}


def test_models_parse_the_wire_shapes():
    s = Sonar.from_dict({"id": "abc", "owner_id": "o", "name": "n", "enabled": True, "spec": SPEC,
                         "cadence": "instant", "channels": [{"type": "push"}], "daily_cap": None,
                         "tier": "free", "created": "2026-09-10T00:00:00Z", "updated": "2026-09-10T00:00:00Z"})
    assert s.id == "abc" and s.spec == SPEC and s.channels == [{"type": "push"}] and s.daily_cap is None
    assert Sonar.from_list([{"id": "a"}, None, {"id": "b"}]) and len(Sonar.from_list([{"id": "a"}, {"id": "b"}])) == 2

    page = {"matches": [{"id": 7, "sonar_id": "abc", "post_id": "p", "matched_at": "2026-09-10T00:00:00Z",
                         "why": {"matched_by": "hashtag"}, "delivered": True}], "next_before": None}
    ms = SonarMatch.from_list(page)
    assert len(ms) == 1 and ms[0].id == 7 and ms[0].why == {"matched_by": "hashtag"} and ms[0].delivered

    p = SonarPreview.from_dict({"window_days": 7, "total": 42, "per_day": [{"day": "2026-09-09T00:00:00.000Z", "count": 42}],
                                "samples": [{"id": "x", "service": "bluesky", "snippet": "…"}]})
    assert p.window_days == 7 and p.total == 42 and len(p.per_day) == 1 and p.samples[0]["service"] == "bluesky"
    assert SonarPreview.from_dict(None) is None and SonarMatch.from_dict({}) is None
