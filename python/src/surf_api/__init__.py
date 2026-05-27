"""Surf API Python SDK — programmatic access to the Surf social platform."""

from .client import SurfClient
from .exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
    SurfScopeError,
)

__version__ = "0.3.0"
__all__ = [
    "SurfClient",
    "AsyncSurfClient",
    "SurfAPIError",
    "SurfAuthError",
    "SurfNotFoundError",
    "SurfRateLimitError",
    "SurfScopeError",
]


def __getattr__(name):
    """Lazy import AsyncSurfClient to avoid requiring httpx for sync-only usage."""
    if name == "AsyncSurfClient":
        from .async_client import AsyncSurfClient
        return AsyncSurfClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
