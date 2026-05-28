# surf-api (Java)

Java SDK for the [Surf](https://surf.social) social platform API. A faithful port of
the Python `surf-api` SDK, targeting **Java 17**.

- HTTP via the built-in `java.net.http.HttpClient` (no third-party HTTP dependency)
- JSON via Jackson; structured responses deserialize into typed model classes in
  the `social.surf.api.model` package
- Genuinely dynamic responses (post/status objects, content/image/audio results)
  remain `Map<String, Object>`, matching how the backend itself returns them
- Errors surface as unchecked `SurfAPIError` subclasses

## Installation

Gradle:

```groovy
dependencies {
    implementation 'social.surf:surf-api:0.2.0'
}
```

Maven:

```xml
<dependency>
  <groupId>social.surf</groupId>
  <artifactId>surf-api</artifactId>
  <version>0.2.0</version>
</dependency>
```

## Quick Start

```java
import social.surf.api.SurfClient;
import social.surf.api.model.Feed;
import java.util.List;
import java.util.Map;

SurfClient client = new SurfClient("surf_sk_live_your_token_here");

// Get feed metadata (typed model)
Feed feed = client.feeds.get("surf/topic/technology");
System.out.println(feed.title() + " by " + feed.author().name());

// Get posts from a feed (posts are dynamic Mastodon-format JSON, kept as maps)
List<Map<String, Object>> posts = client.feeds.getPosts("surf/topic/technology", 10);
for (Map<String, Object> post : posts) {
    System.out.println(post.get("content"));
}

// Search for feeds
Map<String, Object> results = client.search.feeds("artificial intelligence");

// AI feed summary (typed model)
System.out.println(client.ai.feedSummary("surf/topic/technology").feedSummary());
```

## Features

- **Feeds**: Read feeds, posts, trending content, topics
- **Search**: Search feeds, posts, accounts, podcasts, RSS
- **AI Search**: Natural language queries via NLWeb
- **Audio**: Radio stations, daily briefings, transcripts, quizzes
- **Custom Feeds**: Create, update, delete, clone, publish custom feeds
- **Account**: User info, activity, notifications, preferences
- **Media**: Upload images
- **Rate Limiting**: Automatic rate limit tracking via `client.getRateLimit()`
- **Pagination**: Built-in cursor-based pagination via `client.paginate(...)`

## Response Models

Structured endpoints deserialize into immutable Java records in `social.surf.api.model`,
mirroring the backend DTOs. Every model is annotated `@JsonIgnoreProperties(ignoreUnknown
= true)`, so server-side additions never break deserialization.

| Method | Returns |
|--------|---------|
| `feeds.get(surfId)` | `Feed` |
| `feeds.getPosts(...)`, `feeds.getFollowing()` | `List<Map<String, Object>>` (posts are dynamic) |
| `ai.feedSummary(...)` | `FeedSummary` |
| `ai.threadSummary(...)` | `PostSummary` |
| `account.get()`, `account.update(...)` | `Account` |
| `account.getLinks()` | `List<ProfileLink>` |
| `account.addLink(...)`, `account.updateLink(...)` | `ProfileLink` |
| `notifications.list(...)` | `List<Notification>` |
| `customFeeds.list()` | `List<CustomFeed>` |
| `customFeeds.get/create/update/clone/publish/...Operator(...)` | `CustomFeed` |
| `media.upload(...)` | `MediaUploadResponse` |

Everything else (search, single posts, content/image/audio, preferences) returns
`Map<String, Object>` or `byte[]`, matching how the backend returns those payloads.

## Authentication

Get an API token from the [Surf Developer Portal](https://developers.surf.social/devportal/v1/developer/apply).

```java
SurfClient client = new SurfClient("surf_sk_live_your_token_here");

// Check rate limit status after any request
client.feeds.get("surf/topic/technology");
System.out.println(client.getRateLimit());
// RateLimitInfo(remaining=59/60, reset=2026-01-01T00:01:00Z)
```

## Custom Feeds

```java
import social.surf.api.model.CustomFeed;
import social.surf.api.model.NewFeedOperator;

// Create with typed operators. Operator roles:
// source | include | filtering_include | exclude | score.
CustomFeed feed = client.customFeeds.createWithOperators(
    "AI News",
    "Latest AI and ML news",
    List.of(
        NewFeedOperator.source("surf/topic/artificial-intelligence"),
        NewFeedOperator.source("surf/hashtag/machinelearning")
    )
);

// Add another source (returns the updated feed)
feed = client.customFeeds.addOperator(feed.id(),
    Map.of("surfId", "surf/hashtag/llm", "operator", "source"));

// Publish it
client.customFeeds.publish(feed.id());
```

## Audio

```java
// Create a radio station from a feed
Map<String, Object> station = client.audio.createStation("surf/topic/technology");

// Generate a program
Map<String, Object> program = client.audio.generateProgram((String) station.get("id"));

// Get today's briefing
Map<String, Object> briefing = client.audio.getBriefing();

// Convert text to speech (returns MP3 bytes)
byte[] mp3 = client.audio.textToSpeech("Hello from Surf");
```

## AI Feed Builder (streaming)

`buildFeed` returns a lazy `Stream<String>` of Server-Sent Event lines. Consume it
inside a try-with-resources block so the connection is released:

```java
try (var lines = client.ai.buildFeed("a feed about climate tech")) {
    lines.forEach(System.out::println);
}
```

## Pagination

```java
Map<String, Object> params = Map.of("surf_id", "surf/topic/technology", "limit", 50);
for (Object item : client.paginate("/feed/posts", "posts", params, 200)) {
    Map<?, ?> post = (Map<?, ?>) item;
    System.out.println(post.get("title"));
}
```

## Error Handling

```java
import social.surf.api.*;

try {
    client.feeds.get("surf/topic/nonexistent");
} catch (SurfNotFoundError e) {
    System.out.println("Feed not found");
} catch (SurfRateLimitError e) {
    System.out.println("Rate limited. Retry after " + e.getRetryAfter() + " seconds");
} catch (SurfAuthError e) {
    System.out.println("Invalid API token");
}
```

All Surf exceptions extend `SurfAPIError` (an unchecked `RuntimeException`), so you can
catch the base type to handle any API error.

## Configuration

```java
SurfClient client = new SurfClient(
    "surf_sk_live_...",          // api key
    "https://api.surf.social",   // base url (default)
    30                           // request timeout in seconds
);
```

## Building

Built with Gradle (a wrapper is included — no local Gradle install required):

```bash
cd java
./gradlew compileJava   # compile
./gradlew test          # run the test suite
./gradlew jar           # build the jar (build/libs/surf-api-0.2.0.jar)
./gradlew fatJar        # build a self-contained jar with deps bundled (…-0.2.0-all.jar)
```

Requires JDK 17 or newer. The build is pinned to Java 17 source/bytecode via
`options.release = 17`, so it produces Java 17-compatible artifacts even on a newer JDK.

## Links

- [Developer Portal](https://developers.surf.social)
- [API Reference](https://developers.surf.social/devportal/v1/api-docs)
- [Getting Started Guide](https://developers.surf.social/devportal/v1/getting-started)
