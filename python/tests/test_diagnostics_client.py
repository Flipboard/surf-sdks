"""Unit tests for the diagnostics namespace — no live API required.

Verifies the SDK matches the py-services devportal contract: correct method,
the developer-portal host (not the /v1 data API), URL-escaped path segments,
the {ttl_minutes} body, and X-API-Key auth.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import patch, MagicMock

from surf_api import SurfClient


def _mk_resp(status_code=200, json_body=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.headers = headers or {}
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def _capture(client):
    """Patch the client's session and return the mock so we can inspect calls."""
    return patch.object(client._session, "request", return_value=_mk_resp())


DEVPORTAL = "https://surf.social/devportal/v1"


def test_default_devportal_url():
    assert SurfClient(api_key="k").devportal_url == DEVPORTAL


def test_devportal_url_override():
    c = SurfClient(api_key="k", devportal_url="https://devtest.surf.social/devportal/v1/")
    assert c.devportal_url == "https://devtest.surf.social/devportal/v1"


def test_diagnose_self_scoped():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.diagnostics.diagnose()
    method, url = m.call_args.args[0], m.call_args.args[1]
    assert method == "GET"
    assert url == f"{DEVPORTAL}/diagnose"


def test_diagnose_with_app_id_is_escaped():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.diagnostics.diagnose("weird/id space")
    url = m.call_args.args[1]
    assert url == f"{DEVPORTAL}/applications/weird%2Fid%20space/diagnose"


def test_create_bundle_posts_ttl():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.diagnostics.create_bundle(app_id="app1", ttl_minutes=5)
    assert m.call_args.args[0] == "POST"
    assert m.call_args.args[1] == f"{DEVPORTAL}/applications/app1/debug-bundle"
    assert m.call_args.kwargs["json"] == {"ttl_minutes": 5}


def test_get_and_revoke_bundle_escape_token():
    c = SurfClient(api_key="k")
    with _capture(c) as m:
        c.diagnostics.get_bundle("dbg_a/b")
    assert m.call_args.args[0] == "GET"
    assert m.call_args.args[1] == f"{DEVPORTAL}/debug-bundle/dbg_a%2Fb"
    with _capture(c) as m:
        c.diagnostics.revoke_bundle("dbg_a/b")
    assert m.call_args.args[0] == "DELETE"
    assert m.call_args.args[1] == f"{DEVPORTAL}/debug-bundle/dbg_a%2Fb"


def test_diagnostics_does_not_clobber_rate_limit():
    # A devportal response omits X-RateLimit-* headers; a diagnostics call must
    # NOT overwrite the last real data-API rate_limit with zeros.
    from surf_api.client import RateLimitInfo
    c = SurfClient(api_key="k")
    c.rate_limit = RateLimitInfo({"X-RateLimit-Limit": "300", "X-RateLimit-Remaining": "299"})
    with _capture(c):  # _mk_resp() has empty headers (no rate-limit headers)
        c.diagnostics.diagnose()
    assert c.rate_limit.limit == 300 and c.rate_limit.remaining == 299


def test_empty_devportal_url_falls_back_to_default():
    assert SurfClient(api_key="k", devportal_url="").devportal_url == DEVPORTAL


def test_trailing_slash_devportal_url_normalized():
    c = SurfClient(api_key="k", devportal_url="https://surf.social/devportal/v1/")
    with _capture(c) as m:
        c.diagnostics.diagnose()
    assert m.call_args.args[1] == f"{DEVPORTAL}/diagnose"  # no double slash


def test_api_key_header_sent():
    c = SurfClient(api_key="surf_sk_live_abc")
    assert c._session.headers["X-API-Key"] == "surf_sk_live_abc"
