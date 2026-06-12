# Changelog

All notable changes to the Surf API SDKs will be documented here. All SDKs share the same version number.

---

## Unreleased

### Added
- **Nested posts on the `Post` model** — The typed `Post` model now exposes two optional self-referential nested posts: `reblog` (the reposted post, present on reposts) and `quote` (the quoted post, present on quote posts). Available in Python (`reblog` / `quote`), TypeScript (`reblog?` / `quote?`), and Go (`Reblog` / `Quote`); the Java SDK returns raw `Map<String, Object>` for posts and is unaffected.
- **SurfRTBClient** (Python, TypeScript, Go, Java) -- RTB (Real-Time Bidding) client for programmatic ad buying. Uses the same `surf_sk_live_...` API key as `SurfClient` but targets the RTB endpoints. API key must include `rtb:bid` and/or `rtb:reports` scopes.
  - `bid()` -- send OpenRTB 2.5 bid requests with optional `sandbox=True` for testing without real spend
  - `reports()` -- access RTB performance reports with configurable granularity
  - `config()` -- get publisher RTB configuration and tier info
  - `scopes()` -- list available RTB scopes
  - `ads_txt()` / `adsTxt()` / `AdsTxt()` -- fetch your personalized ads.txt entry authorizing Surf as a seller
  - **Tracking is response-driven:** impression, click, win (`nurl`), and billing (`burl`) URLs are pre-built into the bid response and fired verbatim — there is no `event()` method or separate reporting call.
  - **Multi-impression bid requests** are supported: pass multiple `imp` entries in `bid()` and the response returns a bid per fillable impression (keyed by `bid.impid`); each impression can carry its own `ext.surf` feed targeting
  - **Automatic retry** -- RTB calls now retry on 429 (respecting `Retry-After`) and 5xx with capped exponential backoff, matching `SurfClient`. Default 3 retries (up to 4 total attempts), base delay 1s doubling each retry, capped at 60s; set to 0 to disable. Configurable via `max_retries` (Python), `maxRetries` (TypeScript), `WithRTBMaxRetries(n)` (Go), and the `RtbClient(apiKey, baseUrl, maxRetries)` constructor (Java).
  - **Async (Python):** `AsyncSurfRTBClient` mirrors the sync `SurfRTBClient` with `await`able methods and the same retry behavior; exported from `surf_api`.
  - **Test coverage:** per-language RTB integration tests (sandbox `bid()` + `reports()`/`config()`/`scopes()`/`ads_txt()` + an auth/scope error case), gated on `SURF_API_TEST_TOKEN` and run by the shared `test-harness/run_all.sh`; plus expanded Python unit tests for RTB retry behavior.
- **Public pagination helper** — All four SDKs now expose a consistent `paginate()` method for walking cursor-paginated endpoints that return JSON objects (`{"<key>": [...], "cursor": "..."}`). Both `cursor` and `next_cursor` response fields are supported. An optional `limit` parameter caps total items yielded regardless of page count.
  - Python (sync): `SurfClient.paginate(path, key, params, limit=None)` — generator; `_paginate` retained as a backward-compatible alias
  - Python (async): `AsyncSurfClient.paginate(path, key, params, limit=None)` — async generator
  - TypeScript: `client.paginate<T>(path, key, params?, limit?)` — `AsyncGenerator<T>`, usable with `for await...of`
  - Go: `client.Paginate(path, key string, params url.Values, limit int) *Paginator` — `Next() bool` checks whether an item is available (fetches the next page when the buffer is exhausted); `Item() json.RawMessage` returns the current item, advances the internal pointer, and **enforces the call contract** — calling it without a preceding `Next()` or more than once per `Next()` sets `Err()` and returns `nil`; `Err() error` returns any fetch, parse, or misuse error; Go 1.21 compatible
  - Java: already public since v1.0.0; no change
- **Typed operator helpers** — Python, TypeScript, and Go now have a typed `NewFeedOperator` / `FeedOperator` construct matching Java's existing `NewFeedOperator` record, so callers no longer have to hand-build raw maps when creating feeds with sources.
  - Python: `NewFeedOperator` dataclass with `source()` / `of()` factory methods and `to_dict()`; `FeedFilter` dataclass with `to_dict()`; both exported from `surf_api`; `create()` auto-serializes `NewFeedOperator` objects alongside raw dicts; new `create_with_operators(title, operators, description=None)` convenience method on `custom_feeds`
  - TypeScript: exported `FeedOperator` interface (`surfId`, optional `operator`, optional `filters`) with literal-preserving `operator` type (`string & {}`); `create()` keeps `operators?: unknown[]` (fully backwards-compatible); `createWithOperators(title, operators, description?)` is the strongly-typed entry point
  - Go: `Operator` string type with named constants (`OperatorSource`, `OperatorInclude`, `OperatorFilteringInclude`, `OperatorExclude`, `OperatorScore`); `FeedOperator` and `FeedOperatorFilter` structs with `omitempty` JSON tags; `NewFeedOperatorSource(surfID)` and `NewFeedOperator(surfID, op)` constructor funcs; variadic `CreateWithOperators(title, description string, operators ...FeedOperator)` method
- **SurfAgent** -- AI agent with Surf MCP tools pre-loaded, powered by the Claude Agent SDK. Available in **Python and TypeScript only** (Go and Java do not include agent functionality).
  - Python: `SurfAgent` class in `surf_api.agent` with `run()` and `stream()` methods
  - TypeScript: `SurfAgent` class exported from `@surf/api` with `run()` and `stream()` methods
  - Pre-configured MCP connection to `mcp.surf.social` with all 24 Surf tools (including `ask_creator` for per-creator agents)
  - Budget controls via `max_turns` / `max_budget_usd` (Python) or `maxTurns` / `maxBudgetUsd` (TypeScript)
  - **Safety: read-only by default.** Write tools (`create_post`, `save_custom_feed`, `favourite_post`, `set_feed_theme`) are only permitted when `allow_writes=True` (Python) or `allowWrites: true` (TypeScript). 20 read-only tools are allowed by default.
  - Lazy import of Agent SDK -- does not require `claude-agent-sdk` / `@anthropic-ai/claude-agent-sdk` unless `SurfAgent` is used
  - Unit tests for import, instantiation, read/write tool allowlists, and ImportError on missing SDK
- TypeScript, Go, Java: automatic retry with exponential backoff on 429 and 5xx responses — default 3 retries (up to 4 total attempts per call), base delay 1s doubling each retry, all paths capped at 60s, 429 respects `Retry-After` header. Retry count matches Python's default; Python's 5xx/network backoff is uncapped, ours caps at 60s.
- TypeScript: `maxRetries` option on `SurfClientOptions` to configure retry count (default: `3`; set to `0` to disable)
- Go: `WithMaxRetries(n int) ClientOption` passed to `NewClient` to configure retry count (default: `3`; pass `WithMaxRetries(0)` to disable)
- Java: 4-parameter constructor `SurfClient(apiKey, baseUrl, timeoutSeconds, maxRetries)` to configure retry count (default: `3`)

### Fixed

- **Post-action methods now work for Bluesky posts (AT-URI ids).** `favourite`, `unfavourite`, `reblog`/`boost`, `unreblog`/`unboost`, `bookmark`, `unbookmark`, and `deletePost` now percent-encode the post id in the URL path, so Bluesky AT-URIs (`at://did:plc:…/app.bsky.feed.post/…`) route correctly instead of 404ing on the unencoded `://` and `/`. Fixes Python, TypeScript, and Go (Java already encoded the path segment). Numeric Mastodon ids are unaffected (encoding is a no-op for them).

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
- Go, TypeScript, Java: removed `retryOnRateLimit` / `createClient` / `withRateLimitRetry` test helpers — retry is now handled internally by the SDK

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
