"""Surf API Python SDK — programmatic access to the Surf social platform."""

from .client import SurfClient
from .models import (
    Post,
    FeedMeta,
    PostAccount,
    Card,
    MediaAttachment,
    Image,
    ImageSize,
    Topic,
    TopicsResult,
    ResolveResult,
    EnrichmentData,
    ModerationResult,
    ConnectedApp,
    ProfileLink,
)
from .exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
    SurfScopeError,
)

__version__ = "1.0.0"
__all__ = [
    "SurfClient",
    "AsyncSurfClient",
    "SurfOAuth",
    "AsyncSurfOAuth",
    "SurfAPIError",
    "SurfAuthError",
    "SurfNotFoundError",
    "SurfRateLimitError",
    "SurfScopeError",
    "generate_pkce",
    "Post",
    "FeedMeta",
    "PostAccount",
    "Card",
    "MediaAttachment",
    "Image",
    "ImageSize",
    "Topic",
    "TopicsResult",
    "ResolveResult",
    "EnrichmentData",
    "ModerationResult",
    "ConnectedApp",
    "ProfileLink",
]


def __getattr__(name):
    """Lazy imports to avoid requiring httpx for sync-only usage."""
    if name == "AsyncSurfClient":
        from .async_client import AsyncSurfClient
        return AsyncSurfClient
    if name in ("SurfOAuth", "AsyncSurfOAuth", "generate_pkce"):
        from . import oauth
        return getattr(oauth, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
