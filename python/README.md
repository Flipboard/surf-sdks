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
- **Search**: Search feeds, posts, accounts, Bluesky users, podcasts, RSS
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
```

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

## MCP Integration

The Surf API is also available as an [MCP server](https://mcp.surf.social/mcp) for Claude Code and other MCP-compatible clients. See the [API documentation](https://developers.surf.social/devportal/v1/api-docs) for details.

## Links

- [Developer Portal](https://developers.surf.social)
- [API Reference](https://developers.surf.social/devportal/v1/api-docs)
- [Getting Started Guide](https://developers.surf.social/devportal/v1/getting-started)
