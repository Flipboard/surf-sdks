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
from typing import List, Optional


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
class DocumentSummary:
    """Summary of a longform document (standard.site / Leaflet) attached to a post."""
    title: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    tags: Optional[List[str]] = None
    publication_uri: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[DocumentSummary]:
        if not d:
            return None
        return cls(
            title=d.get("title"),
            description=d.get("description"),
            cover_image_url=d.get("cover_image_url"),
            tags=d.get("tags"),
            publication_uri=d.get("publication_uri"),
        )


@dataclass
class PostSafety:
    """Graded content-safety verdict on a post.

    Two orthogonal axes: an ordinal ``rating`` for gating, and a lossless ``labels``
    array carrying Bluesky's own vocabulary verbatim, plus ``source`` for provenance.

    ``rating`` is ``"explicit"`` (pornographic or graphic), ``"suggestive"``
    (non-pornographic nudity, less-intense sexual, drawn/AI suggestive), ``"safe"``
    (affirmatively cleared by a classifier) or ``"unknown"``. ``"unknown"`` is the
    default and its own tier — it does NOT mean safe, and for un-labelled sources it
    is most of the pool. ``safety=sfw`` on the request drops explicit and suggestive
    server-side but keeps unknown; a strict client drops unknown itself using this.

    ``labels`` holds ``porn``, ``sexual``, ``nudity``, ``graphic-media``,
    ``sexual-figurative``, ``bot`` and any future labeler value (open vocabulary —
    unrecognized values are carried, not dropped, and carry no rating weight).

    ``source`` is ``"self-label"`` (author-applied, including a Mastodon content
    warning), ``"bsky-moderation"`` (a Bluesky labeler), ``"flipboard-detection"``
    (our own classifier) or ``"none"`` (no signal, pairs with ``"unknown"``).
    """
    rating: str = "unknown"
    labels: Optional[List[str]] = None
    source: str = "none"

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PostSafety]:
        if not d:
            return None
        return cls(
            rating=d.get("rating") or "unknown",
            labels=d.get("labels"),
            source=d.get("source") or "none",
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
    in_reply_to_id: Optional[str] = None
    in_reply_to_account_id: Optional[str] = None
    account: Optional[PostAccount] = None
    card: Optional[Card] = None
    media_attachments: List[MediaAttachment] = field(default_factory=list)
    reblog: Optional["Post"] = None
    quote: Optional["Post"] = None
    # Surf-specific fields (from ApiResponseTransformers)
    post_type: Optional[str] = None
    topics: Optional[List[str]] = None
    vibes: Optional[dict] = None
    duration: Optional[int] = None
    podcast: Optional[bool] = None
    paywall: Optional[bool] = None
    orientation: Optional[str] = None
    document: Optional[DocumentSummary] = None
    safety: Optional[PostSafety] = None

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
            in_reply_to_id=d.get("in_reply_to_id"),
            in_reply_to_account_id=d.get("in_reply_to_account_id"),
            account=PostAccount.from_dict(d.get("account")),
            card=Card.from_dict(d.get("card")),
            media_attachments=[
                MediaAttachment.from_dict(m) for m in d.get("media_attachments", [])
                if m is not None
            ],
            reblog=Post.from_dict(d.get("reblog")),
            quote=Post.from_dict(d.get("quote")),
            post_type=d.get("post_type"),
            topics=d.get("topics"),
            vibes=d.get("vibes"),
            duration=d.get("duration"),
            podcast=d.get("podcast"),
            paywall=d.get("paywall"),
            orientation=d.get("orientation"),
            document=DocumentSummary.from_dict(d.get("document")),
            safety=PostSafety.from_dict(d.get("safety")),
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


# ==========================================================================
# Podcast intelligence (episode search, guests, mentions, sponsors)
# ==========================================================================

@dataclass
class PodcastEpisodeSearchResult:
    """One transcript chunk matching a semantic podcast episode search."""
    episode_url: str = ""
    episode_url_hash: str = ""  # SHA1 hex of the full audio URL — stable episode ID
    flyf_id: Optional[str] = None  # podcast feed ID (SHA1 hex of the full RSS feed URL)
    podcast_name: Optional[str] = None
    episode_title: Optional[str] = None
    score: float = 0.0  # semantic similarity (0-1, higher is better)
    chunk_start_seconds: Optional[float] = None
    chunk_end_seconds: Optional[float] = None
    preview: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PodcastEpisodeSearchResult]:
        if not d:
            return None
        return cls(
            episode_url=d.get("episode_url", ""),
            episode_url_hash=d.get("episode_url_hash", ""),
            flyf_id=d.get("flyf_id"),
            podcast_name=d.get("podcast_name"),
            episode_title=d.get("episode_title"),
            score=d.get("score", 0.0),
            chunk_start_seconds=d.get("chunk_start_seconds"),
            chunk_end_seconds=d.get("chunk_end_seconds"),
            preview=d.get("preview"),
        )

    @classmethod
    def from_list(cls, data) -> List[PodcastEpisodeSearchResult]:
        """Parse results from an API response (list or dict with 'results')."""
        if isinstance(data, dict):
            data = data.get("results", [])
        if isinstance(data, list):
            return [r for d in data if (r := cls.from_dict(d)) is not None]
        return []


@dataclass
class PodcastGuestAppearance:
    """One detected episode appearance of a podcast guest or host."""
    flyf_id: Optional[str] = None  # podcast feed ID (SHA1 hex of the full RSS feed URL)
    podcast_name: Optional[str] = None
    episode_url: str = ""
    episode_url_hash: str = ""  # SHA1 hex of the full audio URL
    role: Optional[str] = None  # e.g. 'host', 'guest'
    confidence: Optional[float] = None  # detection confidence (0-1)
    speaking_time_seconds: Optional[float] = None
    detected_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PodcastGuestAppearance]:
        if not d:
            return None
        return cls(
            flyf_id=d.get("flyf_id"),
            podcast_name=d.get("podcast_name"),
            episode_url=d.get("episode_url", ""),
            episode_url_hash=d.get("episode_url_hash", ""),
            role=d.get("role"),
            confidence=d.get("confidence"),
            speaking_time_seconds=d.get("speaking_time_seconds"),
            detected_at=d.get("detected_at"),
        )


@dataclass
class PodcastGuest:
    """A podcast guest or host detected via transcript and speaker analysis."""
    name: str = ""
    title: Optional[str] = None  # professional title, when known (e.g. 'CEO')
    organization: Optional[str] = None
    bluesky_handle: Optional[str] = None
    mastodon_handle: Optional[str] = None
    appearances: List[PodcastGuestAppearance] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PodcastGuest]:
        if not d:
            return None
        return cls(
            name=d.get("name", ""),
            title=d.get("title"),
            organization=d.get("organization"),
            bluesky_handle=d.get("bluesky_handle"),
            mastodon_handle=d.get("mastodon_handle"),
            appearances=[
                a for x in d.get("appearances", [])
                if (a := PodcastGuestAppearance.from_dict(x)) is not None
            ],
        )

    @classmethod
    def from_list(cls, data) -> List[PodcastGuest]:
        """Parse guests from an API response (list or dict with 'guests')."""
        if isinstance(data, dict):
            data = data.get("guests", [])
        if isinstance(data, list):
            return [g for d in data if (g := cls.from_dict(d)) is not None]
        return []


@dataclass
class PodcastMention:
    """All mentions of one entity within one episode."""
    episode_url: str = ""
    episode_url_hash: str = ""  # SHA1 hex of the full audio URL
    flyf_id: Optional[str] = None  # podcast feed ID (SHA1 hex of the full RSS feed URL)
    entity: str = ""  # entity name as spoken/recognized (original casing)
    entity_type: str = ""  # 'person', 'organization', or 'location'
    mention_count: int = 0
    first_start_seconds: Optional[float] = None
    timestamps: List[dict] = field(default_factory=list)  # [{'start': s, 'end': s}], up to 50
    created_at: Optional[str] = None  # when the episode was indexed

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PodcastMention]:
        if not d:
            return None
        return cls(
            episode_url=d.get("episode_url", ""),
            episode_url_hash=d.get("episode_url_hash", ""),
            flyf_id=d.get("flyf_id"),
            entity=d.get("entity", ""),
            entity_type=d.get("entity_type", ""),
            mention_count=d.get("mention_count", 0),
            first_start_seconds=d.get("first_start_seconds"),
            timestamps=d.get("timestamps", []) or [],
            created_at=d.get("created_at"),
        )

    @classmethod
    def from_list(cls, data) -> List[PodcastMention]:
        """Parse mentions from an API response (list or dict with 'mentions')."""
        if isinstance(data, dict):
            data = data.get("mentions", [])
        if isinstance(data, list):
            return [m for d in data if (m := cls.from_dict(d)) is not None]
        return []


@dataclass
class PodcastSponsorAd:
    """One classified podcast ad placement in one episode."""
    episode_url: str = ""
    episode_url_hash: str = ""  # SHA1 hex of the full audio URL
    flyf_id: Optional[str] = None  # podcast feed ID (SHA1 hex of the full RSS feed URL)
    company: str = ""  # advertiser company name
    product: Optional[str] = None
    category: Optional[str] = None  # e.g. 'technology', 'finance', 'health'
    ad_format: Optional[str] = None  # e.g. 'host_read', 'produced'
    promo_code: Optional[str] = None
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None
    duration_seconds: Optional[float] = None
    confidence: Optional[float] = None  # ad detection confidence (0-1)
    ad_text_preview: Optional[str] = None  # up to 1024 chars of the ad read
    model_version: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PodcastSponsorAd]:
        if not d:
            return None
        return cls(
            episode_url=d.get("episode_url", ""),
            episode_url_hash=d.get("episode_url_hash", ""),
            flyf_id=d.get("flyf_id"),
            company=d.get("company", ""),
            product=d.get("product"),
            category=d.get("category"),
            ad_format=d.get("ad_format"),
            promo_code=d.get("promo_code"),
            start_seconds=d.get("start_seconds"),
            end_seconds=d.get("end_seconds"),
            duration_seconds=d.get("duration_seconds"),
            confidence=d.get("confidence"),
            ad_text_preview=d.get("ad_text_preview"),
            model_version=d.get("model_version"),
            created_at=d.get("created_at"),
        )

    @classmethod
    def from_list(cls, data) -> List[PodcastSponsorAd]:
        """Parse sponsor ads from an API response (list or dict with 'sponsors')."""
        if isinstance(data, dict):
            data = data.get("sponsors", [])
        if isinstance(data, list):
            return [s for d in data if (s := cls.from_dict(d)) is not None]
        return []


# ==========================================================================
# Podcast intelligence — phase 4 (fact checks, translations, topic seek)
# ==========================================================================

@dataclass
class PodcastFactCheck:
    """One fact-checked claim from a podcast episode."""
    claim_index: int = 0
    claim_text: str = ""
    claim_type: Optional[str] = None  # e.g. 'statistic', 'event', 'quote'
    timestamp_seconds: Optional[float] = None  # where the claim is made
    verdict: str = ""  # e.g. 'verified', 'disputed', 'false', 'unverifiable'
    confidence: Optional[float] = None  # verdict confidence (0-1)
    explanation: Optional[str] = None
    sources: List[dict] = field(default_factory=list)  # citation objects
    search_queries: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PodcastFactCheck]:
        if not d:
            return None
        return cls(
            claim_index=d.get("claim_index", 0),
            claim_text=d.get("claim_text", ""),
            claim_type=d.get("claim_type"),
            timestamp_seconds=d.get("timestamp_seconds"),
            verdict=d.get("verdict", ""),
            confidence=d.get("confidence"),
            explanation=d.get("explanation"),
            sources=d.get("sources", []) or [],
            search_queries=d.get("search_queries", []) or [],
        )

    @classmethod
    def from_list(cls, data) -> List[PodcastFactCheck]:
        """Parse claims from an API response (list or dict with 'fact_checks')."""
        if isinstance(data, dict):
            data = data.get("fact_checks", [])
        if isinstance(data, list):
            return [c for d in data if (c := cls.from_dict(d)) is not None]
        return []


@dataclass
class PodcastTranslation:
    """A stored transcript translation for one episode and language."""
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    translated_transcript: str = ""
    translated_segments: List[dict] = field(default_factory=list)  # timestamped
    audio_url: Optional[str] = None  # translated TTS audio, when generated
    audio_duration_seconds: Optional[float] = None
    tts_voice: Optional[str] = None
    word_count: Optional[int] = None
    original_duration_seconds: Optional[float] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PodcastTranslation]:
        """Parse a translation object, or a full response dict (uses its
        'translation' key). Returns None when absent (the API's 404 shape)."""
        if not d:
            return None
        if "translation" in d and "translated_transcript" not in d:
            return cls.from_dict(d.get("translation"))
        return cls(
            source_language=d.get("source_language"),
            target_language=d.get("target_language"),
            translated_transcript=d.get("translated_transcript", ""),
            translated_segments=d.get("translated_segments", []) or [],
            audio_url=d.get("audio_url"),
            audio_duration_seconds=d.get("audio_duration_seconds"),
            tts_voice=d.get("tts_voice"),
            word_count=d.get("word_count"),
            original_duration_seconds=d.get("original_duration_seconds"),
        )


@dataclass
class PodcastTopicMatch:
    """One transcript passage matching a skip-to-topic query."""
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None
    text_preview: Optional[str] = None
    score: Optional[float] = None  # relevance (higher is more relevant)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional[PodcastTopicMatch]:
        if not d:
            return None
        return cls(
            start_seconds=d.get("start_seconds"),
            end_seconds=d.get("end_seconds"),
            text_preview=d.get("text_preview"),
            score=d.get("score"),
        )

    @classmethod
    def from_list(cls, data) -> List[PodcastTopicMatch]:
        """Parse matches from an API response (list or dict with 'matches')."""
        if isinstance(data, dict):
            data = data.get("matches", [])
        if isinstance(data, list):
            return [m for d in data if (m := cls.from_dict(d)) is not None]
        return []
