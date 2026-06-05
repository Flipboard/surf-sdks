# Changelog

All notable changes to the Surf API SDKs will be documented here. All SDKs share the same version number.

---

## Unreleased

### Added
- **SurfAgent** -- AI agent with Surf MCP tools pre-loaded, powered by the Claude Agent SDK. Available in **Python and TypeScript only** (Go and Java do not include agent functionality).
  - Python: `SurfAgent` class in `surf_api.agent` with `run()` and `stream()` methods
  - TypeScript: `SurfAgent` class exported from `@surf/api` with `run()` and `stream()` methods
  - Pre-configured MCP connection to `mcp.surf.social` with all 8 Surf tools
  - Budget controls via `max_turns` / `max_budget_usd` (Python) or `maxTurns` / `maxBudgetUsd` (TypeScript)
  - Lazy import of Agent SDK -- does not require `claude-agent-sdk` / `@anthropic-ai/claude-agent-sdk` unless `SurfAgent` is used

---

## v1.1.0 -- 2026-06-05

### Added
- **Feed Themes** — All SDKs now support creating and updating custom feeds with visual themes. The theme schema uses semantic color names (`surface`, `surfaceHeader`, `surfaceCard`, `onSurface`, `onHeader`, `accent`) and separates header/image configuration from color configuration, with light/dark mode and responsive compact overrides.
  - Python: `FeedTheme` class with `to_dict()`, accepted by `create()` and `update()`
  - TypeScript: `FeedTheme` and `FeedThemeColorPalette` interfaces, accepted by `create()` and `update()`
  - Go: `FeedTheme` struct with `ToMap()` method
  - Java: `FeedTheme` record with builder and `toMap()`, new `createWithTheme()` and `update(id, fields, theme)` overloads
  - Java: `CustomFeed` record now includes `theme` field for response deserialization

### Changed
- Python: Integration tests now live in `python/tests/` and use the SDK client directly (no external repo dependency)
- Test harness (`run_all.sh`) runs Python tests from the SDK repo instead of py-services
- Java: percent-encode post IDs in status path segments
- Java: remove non-returned "feed_images" parameter
- Go, TypeScript: add `services` filter to `getPosts` / `GetPosts` (align with Python and Java)
- Go: make `service` parameter optional (variadic) on all write methods — `Favourite`, `Unfavourite`, `Boost`, `Unboost`, `Bookmark`, `Unbookmark`, `CreatePost`, `DeletePost`, `Follow`, `Unfollow`. **Source-breaking** for callers that stored these as typed function values or implemented an interface with the old `(string, string)` signature; call-site usage is unaffected.

### Fixed
- Go: `SearchEmptyQuery` test handles 429 rate limit with retry instead of failing

---

## v1.0.0 -- 2026-06-01

Initial public release.

### API Coverage (83 endpoints)

- **Feeds** -- Browse topics, trending, timelines; create/favourite/boost/bookmark/delete posts
- **Search** -- Feeds, posts, accounts, podcasts with filtering and sorting
- **Custom Feeds** -- CRUD with typed operators (topic, hashtag, keyword, RSS, Bluesky/Mastodon users)
- **AI** -- Natural language search, feed summaries, AI feed builder (100/day)
- **Content** -- URL resolve, article extraction, language detection, enrichment
- **Images** -- AI analysis: describe, classify, OCR, object detection
- **Audio** -- Radio stations, briefings, podcasts, TTS, quizzes
- **Account** -- Lookup, profile links, connected apps
- **Notifications** -- Feed and badge counts
- **Preferences** -- Get/set user preferences
- **Analytics** -- Feed performance metrics
- **Media** -- Image upload
- **MCP** -- Model Context Protocol for AI agents

### Authentication

- API tokens (`surf_sk_*`) for server-to-server
- OAuth 2.0 with PKCE (`surf_at_*`) for user-delegated access
- `?service=bluesky|mastodon` parameter for targeting linked accounts

### SDKs

- **Python** -- Sync (`requests`) + async (`httpx`), typed models, OAuth helper, auto-pagination
- **TypeScript** -- Full type definitions, async/await, SSE streaming, OAuth helper
- **Go** -- Idiomatic error handling, typed models, OAuth helper
- **Java** -- Java 17+ records, `java.net.http.HttpClient` (no deps), typed models, Jackson

### Infrastructure

- Rate limiting (Free/Basic/Pro/Enterprise tiers)
- Auto-retry on 429 with Retry-After
- Cursor-based pagination
- Consistent error types across all SDKs
