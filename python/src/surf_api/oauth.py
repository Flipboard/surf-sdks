"""OAuth 2.0 Authorization Code Flow with PKCE for the Surf API.

Usage (sync)::

    from surf_api.oauth import SurfOAuth

    oauth = SurfOAuth(
        client_id="your-app-public-id",
        redirect_uri="https://yourapp.com/callback",
    )

    # Step 1: Generate authorization URL
    auth_url, state, verifier = oauth.get_authorize_url(
        scope="read:feeds write:statuses"
    )
    # Redirect the user to auth_url

    # Step 2: Exchange the code (after redirect back)
    tokens = oauth.exchange_code(code="AUTH_CODE", code_verifier=verifier)
    # tokens = {"access_token": "surf_at_...", "refresh_token": "surf_rt_...", ...}

    # Step 3: Create a client with the access token
    from surf_api import SurfClient
    client = SurfClient(tokens["access_token"])

    # Step 4: Refresh when expired
    new_tokens = oauth.refresh_token(tokens["refresh_token"])

Usage (async)::

    from surf_api.oauth import AsyncSurfOAuth

    oauth = AsyncSurfOAuth(client_id="...", redirect_uri="...")
    tokens = await oauth.exchange_code(code="...", code_verifier="...")
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Optional, Tuple
from urllib.parse import urlencode


DEFAULT_AUTH_URL = "https://surf.social"
DEFAULT_TOKEN_URL = "https://surf.social/oauth/token"
DEFAULT_REVOKE_URL = "https://surf.social/oauth/revoke"


def generate_pkce() -> Tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256).

    Returns:
        (code_verifier, code_challenge) tuple
    """
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


class SurfOAuth:
    """Synchronous OAuth 2.0 helper for the Surf API."""

    def __init__(
        self,
        client_id: str,
        redirect_uri: str,
        auth_base_url: str = DEFAULT_AUTH_URL,
        token_url: str = DEFAULT_TOKEN_URL,
        revoke_url: str = DEFAULT_REVOKE_URL,
    ):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.auth_base_url = auth_base_url.rstrip("/")
        self.token_url = token_url
        self.revoke_url = revoke_url

    def get_authorize_url(
        self,
        scope: str = "read:feeds",
        state: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Build the authorization URL with PKCE.

        Args:
            scope: Space-separated scopes (e.g., "read:feeds write:statuses")
            state: Optional CSRF state value (auto-generated if None)

        Returns:
            (authorize_url, state, code_verifier) — save state and verifier for later
        """
        if state is None:
            state = secrets.token_urlsafe(32)
        verifier, challenge = generate_pkce()

        params = urlencode({
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope,
            "response_type": "code",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        url = f"{self.auth_base_url}/oauth/authorize?{params}"
        return url, state, verifier

    def exchange_code(self, code: str, code_verifier: str) -> dict:
        """Exchange an authorization code for access + refresh tokens.

        Args:
            code: The authorization code from the callback
            code_verifier: The PKCE code_verifier from get_authorize_url()

        Returns:
            {"access_token": "surf_at_...", "refresh_token": "surf_rt_...",
             "token_type": "Bearer", "expires_in": 3600, "scope": "..."}
        """
        import requests
        resp = requests.post(self.token_url, json={
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def refresh_token(self, refresh_token: str) -> dict:
        """Use a refresh token to get a new access token.

        Returns:
            {"access_token": "surf_at_...", "refresh_token": "surf_rt_...", ...}
            Note: the refresh token rotates — the old one is invalidated.
        """
        import requests
        resp = requests.post(self.token_url, json={
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def revoke(self, token: str) -> bool:
        """Revoke an access or refresh token.

        Returns:
            True if revocation was acknowledged
        """
        import requests
        resp = requests.post(self.revoke_url, json={
            "client_id": self.client_id,
            "token": token,
        }, timeout=15)
        return resp.status_code == 200


class AsyncSurfOAuth:
    """Async OAuth 2.0 helper for the Surf API (uses httpx)."""

    def __init__(
        self,
        client_id: str,
        redirect_uri: str,
        auth_base_url: str = DEFAULT_AUTH_URL,
        token_url: str = DEFAULT_TOKEN_URL,
        revoke_url: str = DEFAULT_REVOKE_URL,
    ):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.auth_base_url = auth_base_url.rstrip("/")
        self.token_url = token_url
        self.revoke_url = revoke_url

    def get_authorize_url(
        self,
        scope: str = "read:feeds",
        state: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Build the authorization URL with PKCE. (sync — no I/O needed)"""
        if state is None:
            state = secrets.token_urlsafe(32)
        verifier, challenge = generate_pkce()
        params = urlencode({
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope,
            "response_type": "code",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        url = f"{self.auth_base_url}/oauth/authorize?{params}"
        return url, state, verifier

    async def exchange_code(self, code: str, code_verifier: str) -> dict:
        """Exchange an authorization code for tokens."""
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.token_url, json={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": code_verifier,
            })
            resp.raise_for_status()
            return resp.json()

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an access token."""
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.token_url, json={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": refresh_token,
            })
            resp.raise_for_status()
            return resp.json()

    async def revoke(self, token: str) -> bool:
        """Revoke a token."""
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.revoke_url, json={
                "client_id": self.client_id,
                "token": token,
            })
            return resp.status_code == 200
