# Changelog

All notable changes to the Surf API SDKs will be documented here. All SDKs share the same version number.

---

## Unreleased

### Added
- **Podcast intelligence** (Python sync+async, TypeScript, Go, Java) — the audio namespace now wraps the five podcast-intelligence endpoints (`read:audio` scope). Episodes are identified by `episode_url_hash` (SHA1 hex of the episode's full audio URL) and podcasts by `flyf_id` (SHA1 hex of the RSS feed URL); list endpoints default to 20 rows, max 100, and coverage starts with a pilot subset of podcasts, expanding over time.
  - **Semantic episode search** (`GET /audio/episodes/search`) — natural-language search over transcript chunks via embedding similarity (no keyword overlap required); results carry the matching chunk's time range, a text `preview`, and a similarity `score` (0-1) for deep-linking into the episode. `client.audio.search_podcast_episodes(q, flyf_id=…, limit=…)` (Python); `client.audio.searchPodcastEpisodes(q, { flyf_id?, limit? })` (TypeScript, typed `PodcastEpisodeSearchResponse`); `client.Audio.SearchPodcastEpisodes(q, flyfID, limit)` (Go); `client.audio.searchPodcastEpisodes(q[, flyfId, limit])` (Java).
  - **Guest search** (`GET /audio/guests/search`) — fuzzy name search over detected guests/hosts, each with profile details (title, organization, social handles) and episode `appearances` (role, confidence, speaking time). `search_podcast_guests(q, limit=…)` / `searchPodcastGuests(q, limit?)` / `SearchPodcastGuests(q, limit)` / `searchPodcastGuests(q[, limit])`.
  - **Entity mentions** (`GET /audio/mentions`) — episodes mentioning a person, organization, or location (case-insensitive NER over transcripts), with per-episode mention counts and up to 50 in-episode `timestamps` (`{start, end}` seconds); newest first, `limit`/`offset` paging, optional `entity_type` filter (`person` | `organization` | `location`). `get_podcast_mentions(entity, entity_type=…, flyf_id=…, limit=…, offset=…)` / `getPodcastMentions(entity, { entity_type?, flyf_id?, limit?, offset? })` / `GetPodcastMentions(entity, entityType, flyfID, limit, offset)` / `getPodcastMentions(entity[, entityType, flyfId, limit, offset])`.
  - **Sponsor/ad intelligence** (`GET /audio/sponsors`) — detected and classified ad reads: advertiser, product, category, format, promo code, exact time range, confidence, and an `ad_text_preview`. Query by company or list all ads in one episode (at least one required — the SDKs raise/throw client-side when both are missing: Python `ValueError`, TypeScript `Error`, Go `error`, Java `IllegalArgumentException`). `get_podcast_sponsors(company=…, episode_url_hash=…, episode_url=…, flyf_id=…, limit=…, offset=…)` (Python — `episode_url` is hashed for you); `getPodcastSponsors({ company?, episode_url_hash?, episode_url?, flyf_id?, limit?, offset? })` (TypeScript, same convenience); `GetPodcastSponsors(company, episodeURLHash, flyfID, limit, offset)` (Go); `getPodcastSponsors(company, episodeUrlHash, flyfId, limit, offset)` plus `getPodcastSponsorsByCompany(company)` / `getPodcastSponsorsForEpisode(hash)` conveniences (Java).
  - **Show notes** (`GET /audio/transcripts/show-notes` — existing route, now documented and wrapped) — structured, AI-generated show notes for a transcribed episode (summary, topics, people, organizations, timestamped outline, key takeaways, chapters) plus a `signed_url` for the raw JSON; optional `language` for translated notes; 404 until notes have been generated. `get_show_notes(episode_url, language=…)` / `getShowNotes(episode_url, language?)` (typed `ShowNotesResponse`) / `GetShowNotes(episodeURL, language)` / `getShowNotes(episodeUrl[, language])`.
  - **Hash helper** — every SDK ships a helper computing `episode_url_hash` from a full audio URL: `surf_api.episode_url_sha1(url)` (Python), `episodeUrlHash(url)` (TypeScript export; dependency-free pure-TS SHA-1, so it's synchronous and runtime-agnostic), `surf.EpisodeURLHash(url)` (Go), `AudioApi.episodeUrlHash(url)` (Java static).
  - **Typed models** — Python dataclasses (`PodcastEpisodeSearchResult`, `PodcastGuest` + `PodcastGuestAppearance`, `PodcastMention`, `PodcastSponsorAd`, each with `from_dict`/`from_list`, exported from `surf_api`); TypeScript interfaces (the same set plus per-endpoint response types and `PodcastShowNotes`); Go structs (same set plus response wrappers, available as `json.RawMessage` decode targets). The Java SDK returns raw `Map<String, Object>` for audio, matching the rest of its audio namespace.
- **Podcast intelligence, phase 4** (Python sync+async, TypeScript, Go, Java) — the audio namespace also wraps the four new per-episode endpoints (`read:audio` scope), all keyed by `episode_url` (the episode's full audio/enclosure URL — no hashing needed here) and all retrieval-only: results are produced ahead of time by the ingestion pipeline, and nothing below triggers transcription, translation, or a fact-check run. The catch-up and skip-to-topic endpoints 404 with `error: "transcript not available"` when the episode has no cached transcript yet (queue one via the transcript-request route).
  - **Fact checks** (`GET /audio/fact-checks`) — stored fact-check results in claim order: each claim carries `claim_text`, `claim_type`, `timestamp_seconds`, a `verdict` with `confidence` and `explanation`, plus the `sources` and `search_queries` behind it; `summary` counts claims per verdict. 404 when the episode has no fact checks. `client.audio.get_fact_checks(episode_url)` (Python); `client.audio.getFactChecks(episode_url)` (TypeScript, typed `PodcastFactChecksResponse`); `client.Audio.GetFactChecks(episodeURL)` (Go); `client.audio.getFactChecks(episodeUrl)` (Java).
  - **Translations** (`GET /audio/translations`) — a stored transcript translation for a `language` (`es`, `pt-BR`, …): the full `translated_transcript`, timestamped `translated_segments`, and — when TTS was generated — a translated `audio_url` with duration and voice. Never translates on demand; 404 when no translation exists for the language. `get_translation(episode_url, language)` / `getTranslation(episode_url, language)` (typed `PodcastTranslationResponse`) / `GetTranslation(episodeURL, language)` / `getTranslation(episodeUrl, language)`.
  - **Catch-up** (`GET /audio/catch-up`) — "what did I miss?" summary of everything before a playback position (seconds, 0-86400): prose `summary`, `topics_covered`, `key_points`, and `missed_duration_seconds`. `get_catch_up(episode_url, timestamp_seconds)` / `getCatchUp(episode_url, timestamp_seconds)` (typed `PodcastCatchUpResponse`) / `GetCatchUp(episodeURL, timestampSeconds)` / `getCatchUp(episodeUrl, timestampSeconds)`.
  - **Skip-to-topic** (`GET /audio/skip-to-topic`) — semantic "jump to the part about X" within one episode; `matches` come back best first with `start_seconds`/`end_seconds` for deep-linking, a `text_preview`, and a relevance `score` (empty `matches` with `ok: true` = nothing above the relevance floor; `limit` default 5, max 20). `skip_to_topic(episode_url, topic, limit=…)` / `skipToTopic(episode_url, topic, limit?)` (typed `PodcastTopicSeekResponse`) / `SkipToTopic(episodeURL, topic, limit)` (limit <= 0 uses the server default) / `skipToTopic(episodeUrl, topic[, limit])`.
  - **Typed models** — Python dataclasses `PodcastFactCheck` (`from_dict`/`from_list`), `PodcastTranslation` (`from_dict` accepts either the bare translation object or the full response), and `PodcastTopicMatch` (`from_dict`/`from_list`), exported from `surf_api`; TypeScript interfaces for the same set plus the four response types; Go structs (`PodcastFactCheck`/`PodcastFactChecksResponse`, `PodcastTranslation`/`PodcastTranslationResponse`, `PodcastCatchUpResponse`, `PodcastTopicMatch`/`PodcastTopicSeekResponse`) as `json.RawMessage` decode targets. The Java SDK stays raw `Map<String, Object>`, matching its audio namespace.
- **Phrase and boolean query syntax on post search** (Python sync+async, TypeScript, Go, Java) — the `/search/posts` backend now supports exact phrases in double quotes (`"climate change"`, matched literally with no stemming) and boolean operators `AND`/`&&` and `OR`/`||` between terms (`cats AND dogs`; the word forms are uppercase-only, so natural-language queries like `fish and chips` are unchanged; plain keywords remain implicit AND). The SDKs already pass `q` through verbatim, so no code changes are needed to use it; the `posts()` helper docstrings across all four SDKs now document the syntax.
- **Feed recency window** — feed post retrieval gains a `since` parameter across all four SDKs (Python sync + async, TypeScript, Go, Java) accepting a rolling duration (`24h`, `7d`, `30m`, `90s`, bare seconds) or ISO 8601 timestamp, so only posts within the window are returned. Powers daily-digest use cases; mirrors the MCP `get_feed_posts`/`summarize_feed` `window` argument and the new `daily_digest` MCP prompt. Python: `feeds.get_posts(..., since=)`; TypeScript: `feeds.getPosts(surf_id, { since })`; Go: `PostsOptions{Since: ...}`; Java: `getPosts(surfId, limit, cursor, sort, services, since)`.
- **Longform documents & publications** (Python sync+async, TypeScript, Go, Java) — new `longform` namespace wrapping the standard.site / Leaflet endpoints (blogs and articles published as AT Protocol records). Pass raw AT-URIs (e.g. `at://did:plc:x/site.standard.document/3k2a`) — the SDKs percent-encode them into the path for you. Either lexicon namespace is accepted on input; responses emit canonical `site.standard.*` URIs. Scopes: `read:feeds` (documents/publications), `read:search` (publication search).
  - **Get a document** — sanitized, embed-ready HTML in `content_html` by default; pass format `"blocks"` for the raw AT Protocol page/block structure (`pages`) instead. Includes tags, cover image, author (`did`/`handle`), publication metadata, and `comments_count`.
    - `client.longform.document(uri, format=None)` (Python, sync + async) — returns a dict.
    - `client.longform.getDocument(uri, { format? })` (TypeScript) — returns the typed `Document`.
    - `client.Longform.Document(uri, surf.WithFormat("blocks"))` (Go) — returns `json.RawMessage`; typed `Document` model available as a decode target.
    - `client.longform.getDocument(uri[, format])` (Java) — returns the typed `Document` record.
  - **Get a publication** (blog/site metadata: name, description, icon, publisher handle/avatar) — `client.longform.publication(uri)` (Python); `client.longform.getPublication(uri)` (TypeScript, Java); `client.Longform.Publication(uri)` (Go).
  - **List a publication's documents** — newest first, with repeatable `tags` filters (matches any) and `count`/`from` offset pagination (count default 20, max 100). Returns document summaries; fetch full content with the document call. `client.longform.publication_documents(uri, tags=…, count=…, offset=…)` (Python, `offset` maps to the API's `from`); `client.longform.listDocuments(uri, { tags?, count?, from? })` (TypeScript); `client.Longform.PublicationDocuments(uri, surf.WithTags(…), surf.WithCount(…), surf.WithFrom(…))` (Go); `client.longform.listDocuments(uri[, tags, count, from])` (Java).
  - **Search publications** by name, description, or topic — available both as `client.longform.search_publications(q, …)` / `searchPublications(q, …)` / `SearchPublications(q, …)` and as a `publications(q, …)` helper on the existing search namespace, matching the other per-type search helpers.
  - **`document` summary on posts** — longform document posts returned by feed/search endpoints now carry a lightweight `document` object (title, description, cover image, tags, `publication_uri`); the post `id` is the AT-URI to pass to the document call for full content. Surfaced on the typed `Post` models: `Post.document` (Python `DocumentSummary` dataclass, TypeScript `DocumentSummary`, Go `*PostDocument`); the Java SDK returns raw maps for posts and is unaffected.
- **Fact-checking** (Python sync+async, TypeScript, Go, Java) — wraps the new `POST /ai/fact-check` endpoint (`use:ai` scope). Fact-check a claim, paragraph, or post and get back a structured verdict (`TRUE` / `MOSTLY TRUE` / `MIXED` / `MISLEADING` / `MOSTLY FALSE` / `FALSE` / `UNVERIFIABLE`), a one-line `answer`, per-claim `paragraphs` (each with `citationIndices`), and a flat `citations` list (web sources + the checked post). Powered by Claude with live web search; response fields are camelCase. Provide exactly one of `text` (arbitrary content, e.g. a briefing paragraph) or `postSurfId` (an existing Surf post); optional `feedId` for the post path.
  - `client.ai.fact_check(text=…, post_surf_id=…, feed_id=…)` (Python, sync + async) — returns a dict.
  - `client.ai.factCheck({ text?, postSurfId?, feedId? })` (TypeScript).
  - `client.AI.FactCheck(text, postSurfID, feedID string)` (Go) — returns `json.RawMessage`.
  - `client.ai.factCheck(text[, feedId])` / `client.ai.factCheckPost(postSurfId[, feedId])` (Java) — returns the typed `FactCheck` model.
  - Also exposed as the `fact_check` MCP tool on the Surf MCP server (read-only, requires auth).
- **Trending + bot-filter options on post search** (Python sync+async, TypeScript, Go, Java) — `/search/posts` now takes two more optional params, surfaced on the `posts()` helper:
  - `since` — restrict to a recent window (`"24h"`, `"7d"`, `"30m"`, `"90s"`, or bare seconds). Pair with `sort="top"` for a "recent **and** engaged" (trending) result — engagement-ranked within a fresh window.
  - `automated` — pass `false` to drop bot/bridge-account posts server-side (the softer classes stay filterable via each post's `flipboard.automated_reason`).
  - `sort` now also accepts `"top"` (relevance/engagement) alongside `"recent"` (newest-first); Go's post search gains `sort` for the first time.
  - Shapes: `client.search.posts(q, limit, sort=…, since=…, automated=…)` (Python); `client.search.posts(q, limit, { sort, since, automated })` (TypeScript); `client.Search.Posts(q, limit, surf.WithSort(…), surf.WithSince(…), surf.WithAutomated(…))` (Go); `client.search.posts(q, limit, sort, since, automated)` (Java).

### Fixed
- **Search repointed to current endpoints** (Python sync+async, TypeScript, Go, Java) — `search(type=…)` and the `posts()`/`feeds()`/`accounts()`/`podcasts()` helpers were calling a removed unified `/search` endpoint that now returns `404`. Each type is routed to its live path: `posts`→`/search/posts`, `feeds`→`/search/maestra/feeds`, `accounts`→`/search/bluesky/searchActors`, `podcasts`→`/search/maestra/feeds`, `rss`→`/search/rss/search`. Unknown types now raise a clear error instead of silently 404ing. (Previously only Python and Go were repointed; TypeScript and Java still hit the deprecated `/search` and are now fixed too.)

## v1.2.0 -- 2026-07-02

### Added
- **Diagnostics + confidential debug bundles** (Python, TypeScript, Go, Java) — new diagnostics namespace for the developer portal's agent-debugging surface: `client.diagnostics` (Python/TypeScript), `client.Diagnostics` (Go), `client.diagnostics` (Java). Targets the portal host (`https://surf.social/devportal/v1`) automatically; override with `devportal_url` (Python), `devportalUrl` (TypeScript), `WithDevportalURL(...)` (Go), or `setDevportalUrl(...)` (Java) for non-prod backends.
  - `diagnose(app_id=None)` / `diagnose(appId?)` / `Diagnose(appID)` / `diagnose(appId)` — structured diagnosis (derived findings + token health + usage + error breakdown). With an app API key, omit the app id to diagnose that token's own app.
  - `create_bundle(app_id=None, ttl_minutes=15)` / `createBundle({ appId?, ttlMinutes? })` / `CreateBundle(appID, ttlMinutes)` / `createBundle(appId, ttlMinutes)` — mint a redacted, short-lived snapshot to share with Surf support; returns `share_token` + `share_url`.
  - `get_bundle(token)` / `getBundle(token)` / `GetBundle(token)` / `getBundle(token)` — fetch a shared bundle (no auth; the token is the capability).
  - `revoke_bundle(token)` / `revokeBundle(token)` / `RevokeBundle(token)` / `revokeBundle(token)` — revoke a bundle before it expires.
- **AI cover-image generation** (Python, TypeScript, Go, Java) — Media API methods for generating a feed cover image from a text prompt (Stable Diffusion XL), requiring the `use:ai` scope. **Async submit/poll**: generation runs server-side and can take a couple of minutes (longer than request/CDN timeouts), so it doesn't block.
  - `generate_image` / `generateImage` / `GenerateImage` — submits a job and returns immediately with `{ key, url, status: "pending" }` (Java: typed `GenerateImageJob`; Go: `json.RawMessage`). `skip_refiner` / `skipRefiner` trades quality for speed.
  - `get_generate_image_status` / `getGenerateImageStatus` / `GenerateImageStatus` — polls a job: `{ status: "pending" | "done" | "failed" | "not_found" }`.
  - `generate_image_and_wait` / `generateImageAndWait` / `GenerateImageAndWait` — convenience that submits and polls until done (default every 4s, up to 10 min), returning the image URL; raises/throws on failure or timeout.
  - GPU-bound, so it has its own dedicated **20/day-per-app** cap (separate from the shared 100/day AI pool) plus a 20/day-per-user backstop; over-limit returns `429`.
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
