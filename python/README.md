# surf-api

Python SDK for the [Surf](https://surf.social) social platform API.

## Installation

```bash
pip install surf-api
```

## Quick Start

```python
from surf_api import SurfClient

client = SurfClient("surf_sk_live_your_token_here")

# Get feed metadata
feed = client.feeds.get("surf/topic/technology")
print(feed["title"])

# Get posts from a feed
data = client.feeds.get_posts("surf/topic/technology", limit=10)
for post in data["posts"]:
    print(f"{post['title']} by {post['author']['displayName']}")

# Search for feeds
results = client.search.feeds("artificial intelligence")

# Natural language search (NLWeb)
results = client.search.ask("feeds about sustainable energy", k=5)

# Get trending posts
trending = client.feeds.get_posts("surf/trending/dynamic", limit=10)
```

## Features

- **Feeds**: Read feeds, posts, trending content, topics
- **Search**: Search feeds, posts, accounts, Bluesky users, podcasts, RSS, publications
- **Longform**: standard.site / Leaflet documents & publications
- **AI Search**: Natural language queries via NLWeb
- **Audio**: Radio stations, daily briefings, transcripts, quizzes
- **Custom Feeds**: Create, update, delete, clone, publish custom feeds
- **Account**: User info, activity, notifications, preferences
- **Media**: Upload images
- **Rate Limiting**: Automatic rate limit tracking via `client.rate_limit`
- **Pagination**: Built-in cursor-based pagination

## Authentication

Get an API token from the [Surf Developer Portal](https://developers.surf.social/devportal/v1/developer/apply).

```python
client = SurfClient("surf_sk_live_your_token_here")

# Check rate limit status after any request
print(client.rate_limit)  # RateLimitInfo(remaining=59/60, reset=2026-01-01T00:01:00Z)
```

## Custom Feeds

```python
# Create a custom feed
feed = client.custom_feeds.create(
    title="AI News",
    description="Latest AI and ML news",
    operators=[
        {"surfId": "surf/topic/artificial-intelligence", "operator": "source"},
        {"surfId": "bluesky/user/@ai-news.bsky.social", "operator": "source"},
        {"surfId": "surf/hashtag/machinelearning", "operator": "source"},
    ]
)

# Add a source
client.custom_feeds.add_operator(feed["id"], {
    "surfId": "surf/search_keyword/machine learning", "operator": "source"
})

# Publish it
client.custom_feeds.publish(feed["id"])

# Create a themed feed
from surf_api.client import FeedTheme

theme = FeedTheme(
    header_image="https://cdn.example.com/logo.png",
    header_image_size={"width": 600, "height": 272},
    surface="#EFEADD",
    surface_header="#005F5F",
)
feed = client.custom_feeds.create("Branded Feed", theme=theme)
```

## Longform (standard.site / Leaflet)

Documents and publications are addressed by AT-URI — pass the raw URI, the SDK
percent-encodes it for you.

```python
# Fetch a document (HTML by default; format="blocks" for structured pages)
doc = client.longform.document("at://did:plc:x/site.standard.document/3k2a")
print(doc["title"], doc["content_html"])

# Fetch a publication
pub = client.longform.publication("at://did:plc:x/site.standard.publication/self")

# List a publication's documents (offset maps to the API's `from` param)
docs = client.longform.publication_documents(pub["uri"], tags=["essays"], count=50)

# Search publications (also available as client.search.publications)
pubs = client.longform.search_publications("climate")
```

Posts in feed and search responses may include an optional `document` summary
(`title`, `description`, `cover_image_url`, `tags`, `publication_uri`) when they
link to a longform document.

## Audio

```python
# Create a radio station from a feed
station = client.audio.create_station(feed_surf_id="surf/topic/technology")

# Generate a program
program = client.audio.generate_program(station["id"])

# Get the audio manifest
manifest = client.audio.get_program(station["id"])

# Get today's briefing
briefing = client.audio.get_briefing()

# Get a transcript
transcript = client.audio.get_transcript("surf/post/abc123")
```

## Podcast Intelligence

Search and mine transcribed podcasts (`read:audio` scope). Episodes are
identified by `episode_url_hash` — the SHA1 hex of the full audio URL
(`surf_api.episode_url_sha1(url)` computes it). Coverage starts with a pilot
subset of podcasts and expands over time.

```python
# Semantic episode search — natural language over transcript chunks
hits = client.audio.search_podcast_episodes("episodes about AI agents")
for r in hits["results"]:
    print(r["episode_title"], r["score"], r["chunk_start_seconds"], r["preview"])

# Guest search — fuzzy name match with detected appearances
guests = client.audio.search_podcast_guests("Sam Altman")

# Entity mentions — who/what gets talked about, with in-episode timestamps
mentions = client.audio.get_podcast_mentions("Anthropic", entity_type="organization")

# Sponsor/ad intelligence — by company, or all ads in one episode
ads = client.audio.get_podcast_sponsors(company="Squarespace")
ads = client.audio.get_podcast_sponsors(episode_url="https://cdn.example.com/ep-142.mp3")

# Structured show notes (summary, topics, outline, takeaways, chapters)
notes = client.audio.get_show_notes("https://cdn.example.com/ep-142.mp3")

# Fact checks — stored verdicts per claim, with sources (404 if none yet)
checks = client.audio.get_fact_checks("https://cdn.example.com/ep-142.mp3")

# Stored transcript translation (retrieval only — never translates on demand)
spanish = client.audio.get_translation("https://cdn.example.com/ep-142.mp3", "es")

# "What did I miss?" — summary of everything before a playback position
recap = client.audio.get_catch_up("https://cdn.example.com/ep-142.mp3", 1830.5)

# Semantic skip-to-topic — jump to the part about X (best matches first)
spots = client.audio.skip_to_topic("https://cdn.example.com/ep-142.mp3", "the housing market")
for m in spots["matches"]:
    print(m["start_seconds"], m["score"], m["text_preview"])
```

The phase-4 calls (`get_fact_checks`, `get_translation`, `get_catch_up`,
`skip_to_topic`) are retrieval only and take the raw `episode_url` (no hashing).
Catch-up and skip-to-topic work from the cached transcript and raise
`SurfNotFoundError` until the episode has one.

Typed models are available in `surf_api.models`: `PodcastEpisodeSearchResult`,
`PodcastGuest` (+ `PodcastGuestAppearance`), `PodcastMention`, `PodcastSponsorAd`,
`PodcastFactCheck`, `PodcastTranslation`, and `PodcastTopicMatch` — each with
`from_dict` / `from_list` helpers, e.g.
`PodcastSponsorAd.from_list(client.audio.get_podcast_sponsors(company="Squarespace"))`.

## Error Handling

```python
from surf_api import SurfClient, SurfRateLimitError, SurfAuthError, SurfNotFoundError

client = SurfClient("surf_sk_live_your_token_here")

try:
    feed = client.feeds.get("surf/topic/nonexistent")
except SurfNotFoundError:
    print("Feed not found")
except SurfRateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except SurfAuthError:
    print("Invalid API token")
```

## Configuration

```python
client = SurfClient(
    api_key="surf_sk_live_...",
    base_url="https://api.surf.social",  # default
    timeout=30,                           # request timeout in seconds
)
```

## AI Agent

Build autonomous agents that interact with the social web. Requires `claude-agent-sdk`:

```bash
pip install claude-agent-sdk
```

```python
import asyncio
from surf_api.agent import SurfAgent

async def main():
    agent = SurfAgent(surf_api_key="surf_sk_live_your_token")
    result = await agent.run(
        "Find the top AI feeds on Surf and summarize the latest posts"
    )
    print(result.text)

asyncio.run(main())
```

The agent connects to Surf via MCP with 20 read-only tools enabled by default. To also allow posting, favouriting, and feed creation (24 tools total), set `allow_writes=True`:

```python
agent = SurfAgent(surf_api_key="surf_sk_live_your_token", allow_writes=True)
```

All Claude compute runs on your [Agent SDK credit](https://developers.surf.social/devportal/v1/getting-started#mcp-integration-claude--ai-agents).

## MCP Integration

The Surf API is also available as an [MCP server](https://mcp.surf.social/mcp) for Claude Code and other MCP-compatible clients. See the [API documentation](https://developers.surf.social/devportal/v1/api-docs) for details.

## Links

- [Developer Portal](https://developers.surf.social)
- [API Reference](https://developers.surf.social/devportal/v1/api-docs)
- [Getting Started Guide](https://developers.surf.social/devportal/v1/getting-started)
