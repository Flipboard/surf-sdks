"""Unit tests for client authentication — no live API required.

A client holds exactly one credential and sends exactly one header for it: an app key as
``X-API-Key``, an OAuth access token as ``Authorization: Bearer``. The two are not
interchangeable, because ``X-API-Key`` validates its value as an app key and a JWT sent
there is simply not found.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from surf_api import SurfClient  # noqa: E402


def headers(client):
    return client._session.headers


def test_an_app_key_is_sent_as_x_api_key_and_nothing_else():
    c = SurfClient("surf_sk_live_k")
    assert headers(c)["X-API-Key"] == "surf_sk_live_k"
    assert "Authorization" not in headers(c)


def test_an_access_token_is_sent_as_a_bearer_and_nothing_else():
    c = SurfClient(access_token="jwt-one")
    assert headers(c)["Authorization"] == "Bearer jwt-one"
    assert "X-API-Key" not in headers(c)


def test_a_refreshed_token_replaces_the_header():
    c = SurfClient(access_token="jwt-one")
    c.access_token = "jwt-two"
    assert headers(c)["Authorization"] == "Bearer jwt-two"
    assert "X-API-Key" not in headers(c)
    assert c.access_token == "jwt-two"


def test_switching_credential_kind_clears_the_other_header():
    c = SurfClient("surf_sk_live_k")
    c.access_token = "jwt-one"
    assert headers(c)["Authorization"] == "Bearer jwt-one"
    assert "X-API-Key" not in headers(c), "the app key must not ride along on OAuth calls"
    assert c.api_key is None


@pytest.mark.parametrize("args,kwargs", [((), {}), (("k",), {"access_token": "t"})])
def test_exactly_one_credential_is_required(args, kwargs):
    with pytest.raises(ValueError, match="exactly one"):
        SurfClient(*args, **kwargs)


@pytest.mark.parametrize("attr", ["access_token", "api_key"])
def test_an_empty_credential_is_refused(attr):
    c = SurfClient(access_token="jwt-one")
    with pytest.raises(ValueError, match="cannot be empty"):
        setattr(c, attr, "")


def test_the_async_client_authenticates_the_same_way():
    httpx = pytest.importorskip("httpx")  # noqa: F841
    from surf_api.async_client import AsyncSurfClient

    c = AsyncSurfClient(access_token="jwt-one")
    assert c._client.headers["Authorization"] == "Bearer jwt-one"
    assert "X-API-Key" not in c._client.headers

    c.access_token = "jwt-two"
    assert c._client.headers["Authorization"] == "Bearer jwt-two"

    app = AsyncSurfClient("surf_sk_live_k")
    assert app._client.headers["X-API-Key"] == "surf_sk_live_k"
    assert "Authorization" not in app._client.headers

    with pytest.raises(ValueError, match="exactly one"):
        AsyncSurfClient()
