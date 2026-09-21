"""Unit tests for the playback namespace — no live API required.

Verifies the SDK matches the fldaily /playback contract: method, path, the
body's optional fields being omitted rather than sent as null, the repeated
post_id query parameter, and the local short-circuits.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import patch, MagicMock

from surf_api import SurfClient

BASE = "https://api.surf.social/v1"
SHOW = "surf/podcast/abc"


def _mk_resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.headers = {}
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def _capture(client, json_body=None, status_code=200):
    return patch.object(client._session, "request", return_value=_mk_resp(status_code, json_body))


def test_report_sends_only_what_it_was_given():
    c = SurfClient(api_key="k")
    with _capture(c, status_code=204) as m:
        c.playback.report("p1", SHOW, 125_000)
    assert m.call_args.args[:2] == ("POST", f"{BASE}/playback")
    assert m.call_args.kwargs["json"] == {
        "post_id": "p1", "feed_surf_id": SHOW, "position_ms": 125_000,
    }


def test_an_omitted_duration_is_absent_rather_than_null():
    """The server leaves a known duration alone when a report omits it; sending
    an explicit null would be a different request."""
    c = SurfClient(api_key="k")
    with _capture(c, status_code=204) as m:
        c.playback.report("p1", SHOW, 1, duration_ms=None, completed=None)
    assert "duration_ms" not in m.call_args.kwargs["json"]
    assert "completed" not in m.call_args.kwargs["json"]

    with _capture(c, status_code=204) as m:
        c.playback.report("p1", SHOW, 1, duration_ms=3_600_000, completed=True)
    assert m.call_args.kwargs["json"]["duration_ms"] == 3_600_000
    assert m.call_args.kwargs["json"]["completed"] is True


def test_a_zero_position_is_sent_because_zero_is_a_real_position():
    c = SurfClient(api_key="k")
    with _capture(c, status_code=204) as m:
        c.playback.report("p1", SHOW, 0)
    assert m.call_args.kwargs["json"]["position_ms"] == 0


def test_completed_false_is_sent_explicitly():
    """False is a statement, not an omission: it is how a client says the
    episode is not finished."""
    c = SurfClient(api_key="k")
    with _capture(c, status_code=204) as m:
        c.playback.report("p1", SHOW, 1, completed=False)
    assert m.call_args.kwargs["json"]["completed"] is False


def test_batch_posts_the_items_under_items():
    c = SurfClient(api_key="k")
    items = [
        {"post_id": "p1", "feed_surf_id": SHOW, "position_ms": 10},
        {"post_id": "p2", "feed_surf_id": SHOW, "position_ms": 20},
    ]
    with _capture(c, status_code=204) as m:
        c.playback.report_batch(items)
    assert m.call_args.args[:2] == ("POST", f"{BASE}/playback/batch")
    assert m.call_args.kwargs["json"] == {"items": items}


def test_recent_defaults_and_path():
    c = SurfClient(api_key="k")
    with _capture(c, json_body=[]) as m:
        c.playback.recent()
    assert m.call_args.args[:2] == ("GET", f"{BASE}/playback")
    assert m.call_args.kwargs["params"] == {"limit": 50}

    with _capture(c, json_body=[]) as m:
        c.playback.recent(limit=10)
    assert m.call_args.kwargs["params"] == {"limit": 10}


def test_positions_sends_the_ids_as_a_repeated_param():
    c = SurfClient(api_key="k")
    with _capture(c, json_body=[]) as m:
        c.playback.positions(["a", "b"])
    assert m.call_args.args[:2] == ("GET", f"{BASE}/playback/positions")
    assert m.call_args.kwargs["params"] == {"post_id": ["a", "b"]}


def test_positions_with_nothing_to_ask_makes_no_call():
    """A list screen with no ids should not cost a round trip, and an empty
    post_id would be a 400 rather than an empty answer."""
    c = SurfClient(api_key="k")
    with _capture(c, json_body=[]) as m:
        assert c.playback.positions([]) == []
        assert c.playback.positions(["", None]) == []
    m.assert_not_called()
