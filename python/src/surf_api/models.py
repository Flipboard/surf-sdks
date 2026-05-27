"""Typed response models for the Surf API.

All models are dataclasses with optional fields. They provide IDE autocompletion
and type safety while remaining compatible with raw dict responses.

Usage::

    from surf_api.models import Post, FeedMeta, Account

    feed: FeedMeta = FeedMeta.from_dict(client.feeds.get("surf/topic/technology"))
    posts: list[Post] = Post.from_list(client.feeds.get_posts("surf/topic/technology"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ImageSize:
    """A single image size variant."""
    url: str = ""
    width: int = 0
    height: int = 0

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[ImageSize]:
        if not d:
            return None
        return cls(url=d.get("url", ""), width=d.get("width", 0), height=d.get("height", 0))


@dataclass
class Image:
    """Image with multiple size variants."""
    original: Optional[ImageSize] = None
    xlarge: Optional[ImageSize] = None
    large: Optional[ImageSize] = None
    medium: Optional[ImageSize] = None
    small: Optional[ImageSize] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[Image]:
        if not d:
            return None
        return cls(
            original=ImageSize.from_dict(d.get("original")),
            xlarge=ImageSize.from_dict(d.get("xlarge")),
            large=ImageSize.from_dict(d.get("large")),
            medium=ImageSize.from_dict(d.get("medium")),
            small=ImageSize.from_dict(d.get("small")),
        )


@dataclass
class PostAccount:
    """Author/account information on a post."""
    id: str = ""
    username: str = ""
    display_name: str = ""
    url: str = ""
    avatar: str = ""
    followers_count: int = 0
    following_count: int = 0
    statuses_count: int = 0
    bot: bool = False

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PostAccount]:
        if not d:
            return None
        return cls(
            id=d.get("id", ""),
            username=d.get("username", ""),
            display_name=d.get("display_name", ""),
            url=d.get("url", ""),
            avatar=d.get("avatar", ""),
            followers_count=d.get("followers_count", 0),
            following_count=d.get("following_count", 0),
            statuses_count=d.get("statuses_count", 0),
            bot=d.get("bot", False),
        )


@dataclass
class Card:
    """Link preview card on a post."""
    title: str = ""
    description: str = ""
    url: str = ""
    image: Optional[Image] = None
    type: str = ""  # link, photo, video, rich

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[Card]:
        if not d:
            return None
        return cls(
            title=d.get("title", ""),
            description=d.get("description", ""),
            url=d.get("url", ""),
            image=Image.from_dict(d.get("image")),
            type=d.get("type", ""),
        )


@dataclass
class MediaAttachment:
    """Media attachment on a post."""
    id: str = ""
    type: str = ""  # image, video, gifv, audio
    url: str = ""
    preview_url: str = ""
    description: str = ""

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[MediaAttachment]:
        if not d:
            return None
        return cls(
            id=d.get("id", ""),
            type=d.get("type", ""),
            url=d.get("url", ""),
            preview_url=d.get("preview_url", ""),
            description=d.get("description", ""),
        )


@dataclass
class Post:
    """A post/status from the Surf API (Mastodon-compatible)."""
    id: str = ""
    content: str = ""
    created_at: str = ""
    url: str = ""
    favourites_count: int = 0
    reblogs_count: int = 0
    replies_count: int = 0
    visibility: str = "public"
    sensitive: bool = False
    spoiler_text: str = ""
    language: Optional[str] = None
    account: Optional[PostAccount] = None
    card: Optional[Card] = None
    media_attachments: List[MediaAttachment] = field(default_factory=list)
    # Surf-specific fields (from ApiResponseTransformers)
    post_type: Optional[str] = None
    topics: Optional[List[str]] = None
    vibes: Optional[dict] = None
    duration: Optional[int] = None
    podcast: Optional[bool] = None
    paywall: Optional[bool] = None
    orientation: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[Post]:
        """Parse a post from an API response dict."""
        if not d:
            return None
        return cls(
            id=d.get("id", ""),
            content=d.get("content", ""),
            created_at=d.get("created_at", ""),
            url=d.get("url", ""),
            favourites_count=d.get("favourites_count", 0),
            reblogs_count=d.get("reblogs_count", 0),
            replies_count=d.get("replies_count", 0),
            visibility=d.get("visibility", "public"),
            sensitive=d.get("sensitive", False),
            spoiler_text=d.get("spoiler_text", ""),
            language=d.get("language"),
            account=PostAccount.from_dict(d.get("account")),
            card=Card.from_dict(d.get("card")),
            media_attachments=[
                MediaAttachment.from_dict(m) for m in d.get("media_attachments", [])
                if m is not None
            ],
            post_type=d.get("post_type"),
            topics=d.get("topics"),
            vibes=d.get("vibes"),
            duration=d.get("duration"),
            podcast=d.get("podcast"),
            paywall=d.get("paywall"),
            orientation=d.get("orientation"),
        )

    @classmethod
    def from_list(cls, data) -> List[Post]:
        """Parse a list of posts from an API response (handles both list and dict with 'posts' key)."""
        if isinstance(data, list):
            return [p for d in data if (p := cls.from_dict(d)) is not None]
        if isinstance(data, dict):
            items = data.get("posts", data.get("statuses", []))
            if isinstance(items, list):
                return [p for d in items if (p := cls.from_dict(d)) is not None]
        return []


@dataclass
class FeedMeta:
    """Feed metadata from GET /feed."""
    title: str = ""
    description: str = ""
    type: str = ""
    surf_id: str = ""
    author: str = ""
    image: Optional[Image] = None
    subscribers: int = 0

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[FeedMeta]:
        if not d:
            return None
        return cls(
            title=d.get("title", ""),
            description=d.get("description", ""),
            type=d.get("type", ""),
            surf_id=d.get("surf_id", ""),
            author=d.get("author", ""),
            image=Image.from_dict(d.get("image")),
            subscribers=d.get("subscribers", 0),
        )


@dataclass
class Topic:
    """A topic assignment on a post or URL."""
    name: str = ""
    score: int = 0
    topic_type: str = ""

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[Topic]:
        if not d:
            return None
        return cls(name=d.get("name", ""), score=d.get("score", 0), topic_type=d.get("topic_type", ""))


@dataclass
class TopicsResult:
    """Response from GET /content/topics."""
    url: str = ""
    topics: List[Topic] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    post_types: List[str] = field(default_factory=list)
    language: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[TopicsResult]:
        if not d:
            return None
        return cls(
            url=d.get("url", ""),
            topics=[Topic.from_dict(t) for t in d.get("topics", []) if t],
            tags=d.get("tags", []),
            post_types=d.get("post_types", []),
            language=d.get("language"),
        )


@dataclass
class ResolveResult:
    """Response from GET /content/resolve."""
    input_url: str = ""
    final_url: str = ""
    status: int = 0
    chain: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[ResolveResult]:
        if not d:
            return None
        return cls(
            input_url=d.get("input_url", ""),
            final_url=d.get("final_url", ""),
            status=d.get("status", 0),
            chain=d.get("chain", []),
        )


@dataclass
class EnrichmentData:
    """Response from GET /content/enrich."""
    post_id: str = ""
    topics: List[Topic] = field(default_factory=list)
    post_types: List[str] = field(default_factory=list)
    language: Optional[str] = None
    nsfw: bool = False
    claim_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    contains_url: bool = False
    flus_url: Optional[str] = None
    flus_domain: Optional[str] = None
    domain_boost: float = 0.0
    duration: Optional[int] = None
    podcast: bool = False
    orientation: Optional[str] = None
    paywall: bool = False
    favourites_count: int = 0
    reblogs_count: int = 0
    replies_count: int = 0

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[EnrichmentData]:
        if not d:
            return None
        return cls(
            post_id=d.get("post_id", ""),
            topics=[Topic.from_dict(t) for t in d.get("topics", []) if t],
            post_types=d.get("post_types", []),
            language=d.get("language"),
            nsfw=d.get("nsfw", False),
            claim_score=d.get("claim_score", 0.0),
            tags=d.get("tags", []),
            contains_url=d.get("contains_url", False),
            flus_url=d.get("flus_url"),
            flus_domain=d.get("flus_domain"),
            domain_boost=d.get("domain_boost", 0.0),
            duration=d.get("duration"),
            podcast=d.get("podcast", False),
            orientation=d.get("orientation"),
            paywall=d.get("paywall", False),
            favourites_count=d.get("favourites_count", 0),
            reblogs_count=d.get("reblogs_count", 0),
            replies_count=d.get("replies_count", 0),
        )


@dataclass
class ModerationResult:
    """Response from GET /image/moderate."""
    nsfw: bool = False
    moderated: bool = False
    moderation_labels: List[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[ModerationResult]:
        if not d:
            return None
        return cls(
            nsfw=d.get("nsfw", False),
            moderated=d.get("moderated", False),
            moderation_labels=d.get("moderationLabels", []),
        )


@dataclass
class ConnectedApp:
    """An OAuth-authorized third-party app."""
    authorization_id: int = 0
    app_id: str = ""
    app_name: str = ""
    logo_url: Optional[str] = None
    scopes: str = ""
    authorized_at: str = ""
    last_used: str = ""

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[ConnectedApp]:
        if not d:
            return None
        return cls(
            authorization_id=d.get("authorization_id", 0),
            app_id=d.get("app_id", ""),
            app_name=d.get("app_name", ""),
            logo_url=d.get("logo_url"),
            scopes=d.get("scopes", ""),
            authorized_at=d.get("authorized_at", ""),
            last_used=d.get("last_used", ""),
        )

    @classmethod
    def from_list(cls, data) -> List[ConnectedApp]:
        if isinstance(data, list):
            return [a for d in data if (a := cls.from_dict(d)) is not None]
        return []


@dataclass
class ProfileLink:
    """A profile link on the user's profile."""
    id: str = ""
    title: str = ""
    url: str = ""
    icon: Optional[str] = None
    order: int = 0

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[ProfileLink]:
        if not d:
            return None
        return cls(
            id=d.get("id", ""),
            title=d.get("title", ""),
            url=d.get("url", ""),
            icon=d.get("icon"),
            order=d.get("order", 0),
        )
