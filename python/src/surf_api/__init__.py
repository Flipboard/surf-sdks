"""Surf API Python SDK — programmatic access to the Surf social platform."""

from .client import (
    SurfClient,
    SurfRTBClient,
    FeedTheme,
    NewFeedOperator,
    FeedFilter,
    episode_url_sha1,
)
from .models import (
    Post,
    DocumentSummary,
    PostSafety,
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
    PodcastEpisodeSearchResult,
    PodcastGuest,
    PodcastGuestAppearance,
    PodcastMention,
    PodcastSponsorAd,
    PodcastFactCheck,
    PodcastTranslation,
    PodcastTopicMatch,
    PopularShow,
    PopularEpisode,
)
from .exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
    SurfScopeError,
)

__version__ = "1.3.0"
__all__ = [
    "SurfClient",
    "SurfRTBClient",
    "FeedTheme",
    "NewFeedOperator",
    "FeedFilter",
    "AsyncSurfClient",
    "AsyncSurfRTBClient",
    "SurfAgent",
    "SurfOAuth",
    "AsyncSurfOAuth",
    "SurfAPIError",
    "SurfAuthError",
    "SurfNotFoundError",
    "SurfRateLimitError",
    "SurfScopeError",
    "generate_pkce",
    "Post",
    "DocumentSummary",
    "PostSafety",
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
    "PodcastEpisodeSearchResult",
    "PodcastGuest",
    "PodcastGuestAppearance",
    "PodcastMention",
    "PodcastSponsorAd",
    "PodcastFactCheck",
    "PodcastTranslation",
    "PodcastTopicMatch",
    "PopularShow",
    "PopularEpisode",
    "episode_url_sha1",
]


def __getattr__(name):
    """Lazy imports to avoid requiring httpx for sync-only usage."""
    if name == "AsyncSurfClient":
        from .async_client import AsyncSurfClient
        return AsyncSurfClient
    if name == "AsyncSurfRTBClient":
        from .async_client import AsyncSurfRTBClient
        return AsyncSurfRTBClient
    if name == "SurfAgent":
        from .agent import SurfAgent
        return SurfAgent
    if name in ("SurfOAuth", "AsyncSurfOAuth", "generate_pkce"):
        from . import oauth
        return getattr(oauth, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
