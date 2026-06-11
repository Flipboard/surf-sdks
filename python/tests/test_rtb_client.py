"""Unit tests for SurfRTBClient — no live API required."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import patch, MagicMock
from surf_api import SurfRTBClient


def _mk_resp(status_code, json_body=None, text="", headers=None):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.headers = headers or {}
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


class TestSurfRTBClientInit:
    def test_default_base_url(self):
        c = SurfRTBClient(api_key="test-key")
        assert c.base_url == "https://surf.social"

    def test_custom_base_url(self):
        c = SurfRTBClient(api_key="test-key", base_url="https://custom.example.com/")
        assert c.base_url == "https://custom.example.com"

    def test_api_key_in_headers(self):
        c = SurfRTBClient(api_key="surf_sk_live_test123")
        assert c._session.headers["X-API-Key"] == "surf_sk_live_test123"

    def test_no_bearer_auth_header(self):
        c = SurfRTBClient(api_key="test-key")
        assert "Authorization" not in c._session.headers

    def test_default_max_retries(self):
        c = SurfRTBClient(api_key="test-key")
        assert c.max_retries == 3

    def test_custom_max_retries(self):
        c = SurfRTBClient(api_key="test-key", max_retries=5)
        assert c.max_retries == 5


class TestSurfRTBClientURLs:
    def test_bid_url(self):
        c = SurfRTBClient(api_key="k")
        assert c._url("/bid") == "https://surf.social/devportal/v1/rtb/bid"

    def test_reports_url(self):
        c = SurfRTBClient(api_key="k")
        assert c._url("/reports") == "https://surf.social/devportal/v1/rtb/reports"

    def test_config_url(self):
        c = SurfRTBClient(api_key="k")
        assert c._url("/config") == "https://surf.social/devportal/v1/rtb/config"

    def test_scopes_url(self):
        c = SurfRTBClient(api_key="k")
        assert c._url("/scopes") == "https://surf.social/devportal/v1/rtb/scopes"

    def test_ads_txt_url(self):
        c = SurfRTBClient(api_key="k")
        assert c._url("/ads-txt") == "https://surf.social/devportal/v1/rtb/ads-txt"


class TestSurfRTBClientAdsTxt:
    @patch("surf_api.client.requests.Session")
    def test_ads_txt_calls_endpoint(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.return_value = _mk_resp(200, {
            "ok": True, "seller_id": "app_abc",
            "entries": ["surf.social, app_abc, DIRECT"],
        })
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="k")
        c._session = mock_session
        result = c.ads_txt()
        assert result["entries"] == ["surf.social, app_abc, DIRECT"]
        # Verify it hit the ads-txt endpoint
        call_method, call_url = mock_session.request.call_args[0][0], mock_session.request.call_args[0][1]
        assert call_method == "GET"
        assert call_url.endswith("/devportal/v1/rtb/ads-txt")


class TestSurfRTBClientBid:
    @patch("surf_api.client.requests.Session")
    def test_sandbox_adds_test_flag(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.return_value = _mk_resp(200, {"id": "req-1", "seatbid": []})
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="k")
        c._session = mock_session
        c.bid({"id": "req-1", "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}]}, sandbox=True)

        body = mock_session.request.call_args[1]["json"]
        # The body should have test=1 when sandbox=True
        assert body is not None
        assert body.get("test") == 1

    @patch("surf_api.client.requests.Session")
    def test_non_sandbox_no_test_flag(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.request.return_value = _mk_resp(200, {"id": "req-1", "seatbid": []})
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="k")
        c._session = mock_session
        req = {"id": "req-1", "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}]}
        c.bid(req)

        body = mock_session.request.call_args[1]["json"]
        assert body is not None
        assert "test" not in body


class TestSurfRTBClientErrors:
    @patch("surf_api.client.requests.Session")
    def test_401_raises_auth_error(self, mock_session_cls):
        from surf_api.exceptions import SurfAuthError
        mock_session = MagicMock()
        mock_session.request.return_value = _mk_resp(401, text="Unauthorized")
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="bad-key")
        c._session = mock_session

        import pytest
        with pytest.raises(SurfAuthError):
            c.bid({"id": "1", "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}]})

    @patch("surf_api.client.requests.Session")
    def test_429_raises_rate_limit_error(self, mock_session_cls):
        # 429 must raise SurfRateLimitError specifically (a subclass-aware check),
        # not just the generic SurfAPIError. Use max_retries=0 so it raises
        # immediately rather than retrying.
        from surf_api.exceptions import SurfRateLimitError
        mock_session = MagicMock()
        mock_session.request.return_value = _mk_resp(429, text="Rate limited",
                                                     headers={"Retry-After": "5"})
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="k", max_retries=0)
        c._session = mock_session

        import pytest
        with pytest.raises(SurfRateLimitError) as exc_info:
            c.bid({"id": "1", "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}]})
        # Retry-After should be surfaced on the exception
        assert exc_info.value.retry_after == "5"


class TestSurfRTBClientRetry:
    @patch("time.sleep", return_value=None)
    @patch("surf_api.client.requests.Session")
    def test_429_then_success(self, mock_session_cls, mock_sleep):
        # First response 429 (with Retry-After), then 200 -> should retry and succeed.
        mock_session = MagicMock()
        mock_session.request.side_effect = [
            _mk_resp(429, text="slow down", headers={"Retry-After": "1"}),
            _mk_resp(200, {"id": "req-1", "seatbid": [{"bid": []}]}),
        ]
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="k", max_retries=3)
        c._session = mock_session
        result = c.bid({"id": "req-1", "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}]})

        assert result["id"] == "req-1"
        assert mock_session.request.call_count == 2
        # Honored Retry-After (1s) on the 429.
        mock_sleep.assert_called_once_with(1)

    @patch("time.sleep", return_value=None)
    @patch("surf_api.client.requests.Session")
    def test_5xx_then_success(self, mock_session_cls, mock_sleep):
        # 503 then 200 -> should retry with exponential backoff and succeed.
        mock_session = MagicMock()
        mock_session.request.side_effect = [
            _mk_resp(503, text="unavailable"),
            _mk_resp(200, {"summary": {}, "timeseries": []}),
        ]
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="k", max_retries=3)
        c._session = mock_session
        result = c.reports(days=7)

        assert "summary" in result
        assert mock_session.request.call_count == 2
        # Backoff 2**0 == 1 on the first retry.
        mock_sleep.assert_called_once_with(1)

    @patch("time.sleep", return_value=None)
    @patch("surf_api.client.requests.Session")
    def test_max_retries_exhausted_raises(self, mock_session_cls, mock_sleep):
        # Persistent 503 -> retries exhausted -> SurfAPIError raised by _check.
        from surf_api.exceptions import SurfAPIError
        mock_session = MagicMock()
        mock_session.request.return_value = _mk_resp(503, text="still down")
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="k", max_retries=2)
        c._session = mock_session

        import pytest
        with pytest.raises(SurfAPIError) as exc_info:
            c.bid({"id": "1", "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}]})
        assert exc_info.value.status_code == 503
        # max_retries=2 => 3 total attempts.
        assert mock_session.request.call_count == 3
        # Two backoff sleeps (after the first two failed attempts).
        assert mock_sleep.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("surf_api.client.requests.Session")
    def test_429_exhausted_raises_rate_limit(self, mock_session_cls, mock_sleep):
        # Persistent 429 -> retries exhausted -> SurfRateLimitError raised by _check.
        from surf_api.exceptions import SurfRateLimitError
        mock_session = MagicMock()
        mock_session.request.return_value = _mk_resp(429, text="nope",
                                                     headers={"Retry-After": "2"})
        mock_session.headers = {}
        mock_session_cls.return_value = mock_session

        c = SurfRTBClient(api_key="k", max_retries=2)
        c._session = mock_session

        import pytest
        with pytest.raises(SurfRateLimitError):
            c.config()
        assert mock_session.request.call_count == 3
