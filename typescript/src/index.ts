/**
 * Surf API TypeScript/JavaScript SDK
 *
 * @example
 * ```ts
 * import { SurfClient } from '@surf/api';
 *
 * const client = new SurfClient({ apiKey: 'surf_sk_live_...' });
 * const feed = await client.feeds.get('surf/topic/technology');
 * const posts = await client.feeds.getPosts('surf/topic/technology');
 * const summary = await client.ai.feedSummary('surf/topic/technology');
 * ```
 */

import type {
  SurfClientOptions,
  RateLimitInfo,
  SurfErrorBody,
  FeedMeta,
  Post,
  PostAccount,
  ProfileLink,
  ModerationResult,
  EnrichmentData,
  TopicsResult,
  ResolveResult,
  ConnectedApp,
} from './types';

export * from './types';
export { SurfOAuth, generatePKCE } from './oauth';
export type { SurfOAuthOptions, AuthorizeUrlResult, OAuthTokens } from './oauth';
export { SurfAgent } from './agent';
export type { SurfAgentOptions, SurfAgentResult } from './agent';

const DEFAULT_BASE_URL = 'https://api.surf.social';
// Developer-portal endpoints (diagnostics, debug bundles) live on a different
// host/prefix than the v1 data API. Overridable for non-prod backends.
const DEFAULT_DEVPORTAL_URL = 'https://surf.social/devportal/v1';
const API_PREFIX = '/v1';

// ==========================================================================
// Errors
// ==========================================================================

export class SurfAPIError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public errorCode?: string,
  ) {
    super(message);
    this.name = 'SurfAPIError';
  }
}
export class SurfAuthError extends SurfAPIError {
  constructor(message: string, statusCode = 401) {
    super(message, statusCode, 'unauthorized');
    this.name = 'SurfAuthError';
  }
}
export class SurfScopeError extends SurfAPIError {
  constructor(message: string) {
    super(message, 403, 'insufficient_scope');
    this.name = 'SurfScopeError';
  }
}
export class SurfNotFoundError extends SurfAPIError {
  constructor(message: string) {
    super(message, 404, 'not_found');
    this.name = 'SurfNotFoundError';
  }
}
export class SurfRateLimitError extends SurfAPIError {
  constructor(
    message: string,
    public retryAfter?: number,
  ) {
    super(message, 429, 'rate_limit_exceeded');
    this.name = 'SurfRateLimitError';
  }
}

// ==========================================================================
// Client
// ==========================================================================

export class SurfClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly devportalUrl: string;
  private readonly timeout: number;
  private readonly maxRetries: number;
  private readonly _fetch: typeof fetch;

  /** Last rate limit info from any request. */
  public rateLimit: RateLimitInfo | null = null;

  // Sub-clients
  public readonly feeds: FeedsAPI;
  public readonly search: SearchAPI;
  public readonly ai: AIAPI;
  public readonly account: AccountAPI;
  public readonly content: ContentAPI;
  public readonly images: ImagesAPI;
  public readonly audio: AudioAPI;
  public readonly notifications: NotificationsAPI;
  public readonly preferences: PreferencesAPI;
  public readonly customFeeds: CustomFeedsAPI;
  public readonly media: MediaAPI;
  public readonly diagnostics: DiagnosticsAPI;

  constructor(options: SurfClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, '');
    this.devportalUrl = (options.devportalUrl || DEFAULT_DEVPORTAL_URL).replace(/\/+$/, '');
    this.timeout = options.timeout ?? 30_000;
    const r = options.maxRetries ?? 3;
    this.maxRetries = Number.isFinite(r) ? Math.max(0, Math.floor(r)) : 3;
    this._fetch = options.fetch ?? globalThis.fetch;

    this.feeds = new FeedsAPI(this);
    this.search = new SearchAPI(this);
    this.ai = new AIAPI(this);
    this.account = new AccountAPI(this);
    this.content = new ContentAPI(this);
    this.images = new ImagesAPI(this);
    this.audio = new AudioAPI(this);
    this.notifications = new NotificationsAPI(this);
    this.preferences = new PreferencesAPI(this);
    this.customFeeds = new CustomFeedsAPI(this);
    this.media = new MediaAPI(this);
    this.diagnostics = new DiagnosticsAPI(this);
  }

  /** @internal */
  async _request<T = any>(method: string, path: string, opts?: {
    params?: Record<string, string | number | boolean | undefined>;
    json?: unknown;
    raw?: boolean;
    /** When true, `path` is treated as a full URL (no base/prefix prepended). */
    absolute?: boolean;
  }): Promise<T> {
    let url = opts?.absolute ? path : `${this.baseUrl}${API_PREFIX}${path}`;
    if (opts?.params) {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(opts.params)) {
        if (v !== undefined && v !== null) qs.set(k, String(v));
      }
      const s = qs.toString();
      if (s) url += `?${s}`;
    }

    const headers: Record<string, string> = {
      'X-API-Key': this.apiKey,
      'User-Agent': 'surf-api-ts/1.0.0',
    };
    let body: string | undefined;
    if (opts?.json !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(opts.json);
    }
    if (!opts?.raw) {
      headers['Accept'] = 'application/json';
    }

    const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));
    let lastErr: unknown;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      let fetchSucceeded = false;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeout);
      try {
        const resp = await this._fetch(url, {
          method,
          headers,
          body,
          signal: controller.signal,
        });

        // Only update from responses that carry rate-limit headers — devportal
        // (diagnostics) responses omit them and would otherwise clobber the last
        // real data-API rateLimit with zeros.
        const rlLimit = resp.headers.get('X-RateLimit-Limit');
        if (rlLimit !== null) {
          this.rateLimit = {
            limit: parseInt(rlLimit),
            remaining: parseInt(resp.headers.get('X-RateLimit-Remaining') ?? '0'),
            reset: resp.headers.get('X-RateLimit-Reset'),
          };
        }

        if (resp.status === 429 && attempt < this.maxRetries) {
          clearTimeout(timer);
          const raw = parseInt(resp.headers.get('Retry-After') ?? '');
          const retryAfter = Math.min(Number.isFinite(raw) && raw > 0 ? raw : Math.pow(2, attempt), 60);
          try { await resp.body?.cancel(); } catch {}
          await sleep(retryAfter * 1_000);
          continue;
        }

        if (resp.status >= 500 && attempt < this.maxRetries) {
          clearTimeout(timer);
          try { await resp.body?.cancel(); } catch {}
          await sleep(Math.min(Math.pow(2, attempt), 60) * 1_000);
          continue;
        }

        if (!resp.ok) {
          let errBody: Partial<SurfErrorBody> = {};
          try { errBody = await resp.json(); } catch {}
          const msg = errBody.error_description ?? errBody.error ?? resp.statusText;
          if (resp.status === 401) throw new SurfAuthError(msg);
          if (resp.status === 403) throw new SurfScopeError(msg);
          if (resp.status === 404) throw new SurfNotFoundError(msg);
          if (resp.status === 429) {
            const rawRetry = parseInt(resp.headers.get('Retry-After') ?? '');
            const retry = Number.isFinite(rawRetry) && rawRetry > 0 ? rawRetry : 60;
            throw new SurfRateLimitError(msg, retry);
          }
          throw new SurfAPIError(msg, resp.status, errBody.error);
        }

        if (opts?.raw) return resp as unknown as T;
        if (resp.status === 204) return {} as T;
        // Tag successful-fetch scope: errors below (e.g. JSON parse) must not be retried.
        fetchSucceeded = true;
        return await resp.json() as T;
      } catch (e) {
        if (e instanceof SurfAPIError) throw e;
        if (fetchSucceeded) throw e;
        lastErr = e;
        if (attempt < this.maxRetries) {
          clearTimeout(timer);
          await sleep(Math.min(Math.pow(2, attempt), 60) * 1_000);
        }
      } finally {
        clearTimeout(timer);
      }
    }
    throw lastErr ?? new SurfAPIError('Request failed', 0, 'connection_error');
  }

  /**
   * Auto-paginate through a cursor-paginated endpoint, yielding individual items.
   *
   * @param path   API path (e.g. `/feed/posts`)
   * @param key    Response key whose value is the items array (e.g. `"posts"`)
   * @param params Base query parameters (shallow-copied; not mutated)
   * @param limit  Maximum items to yield. Omit, pass `undefined`, or pass a
   *               non-positive value (`0`, negative) for no limit.
   *
   * @example
   * ```ts
   * for await (const post of client.paginate('/feed/posts', 'posts', { surf_id: 'surf/topic/technology' })) {
   *   console.log(post);
   * }
   * ```
   */
  async *paginate<T = any>(
    path: string,
    key: string,
    params?: Record<string, any>,
    limit?: number,
  ): AsyncGenerator<T> {
    const p: Record<string, any> = { ...(params ?? {}) };
    let fetched = 0;
    while (true) {
      if (limit != null && limit > 0 && fetched >= limit) break;
      const data: any = await this._get(path, p);
      if (data === null || typeof data !== 'object' || Array.isArray(data)) {
        const kind = data === null ? 'null' : Array.isArray(data) ? 'array' : typeof data;
        throw new SurfAPIError(
          `paginate: expected a JSON object response from '${path}', got ${kind}`,
          0, 'invalid_response',
        );
      }
      if (!Object.prototype.hasOwnProperty.call(data, key)) break; // missing key → stop cleanly
      if (!Array.isArray(data[key])) {
        const valKind = data[key] === null ? 'null' : typeof data[key];
        throw new SurfAPIError(
          `paginate: expected '${key}' to be an array, got ${valKind}`,
          0, 'invalid_response',
        );
      }
      const items: T[] = data[key];
      if (items.length === 0) break;
      for (const item of items) {
        yield item;
        fetched++;
        if (limit != null && limit > 0 && fetched >= limit) return;
      }
      const cursor = data.cursor || data.next_cursor;
      if (!cursor) break;
      p.cursor = cursor;
    }
  }

  /** @internal */
  _get<T = any>(path: string, params?: Record<string, any>): Promise<T> {
    return this._request<T>('GET', path, { params });
  }
  /** @internal */
  _post<T = any>(path: string, json?: unknown): Promise<T> {
    return this._request<T>('POST', path, { json });
  }
  /** @internal */
  _put<T = any>(path: string, json?: unknown): Promise<T> {
    return this._request<T>('PUT', path, { json });
  }
  /** @internal */
  _patch<T = any>(path: string, json?: unknown): Promise<T> {
    return this._request<T>('PATCH', path, { json });
  }
  /** @internal */
  _delete<T = any>(path: string): Promise<T> {
    return this._request<T>('DELETE', path);
  }

  // Developer-portal helpers (diagnostics, debug bundles) — different host.
  /** @internal */
  _dpGet<T = any>(path: string, params?: Record<string, any>): Promise<T> {
    return this._request<T>('GET', `${this.devportalUrl}${path}`, { params, absolute: true });
  }
  /** @internal */
  _dpPost<T = any>(path: string, json?: unknown): Promise<T> {
    return this._request<T>('POST', `${this.devportalUrl}${path}`, { json, absolute: true });
  }
  /** @internal */
  _dpDelete<T = any>(path: string): Promise<T> {
    return this._request<T>('DELETE', `${this.devportalUrl}${path}`, { absolute: true });
  }
}

// ==========================================================================
// Feeds
// ==========================================================================

/** Feed and post operations. */
class FeedsAPI {
  constructor(private c: SurfClient) {}

  get(surf_id: string): Promise<FeedMeta> { return this.c._get('/feed', { surf_id }); }
  getPosts(surf_id: string, opts?: { limit?: number; cursor?: string; sort?: string; services?: string }): Promise<Post[]> {
    return this.c._get('/feed/posts', { surf_id, ...opts });
  }
  getPost(id: string, thread = false) {
    return this.c._get('/post', { id, thread: thread ? 'true' : undefined });
  }
  getFollowing(limit = 50) { return this.c._get('/feed/following', { limit }); }
  getSpeedDial() { return this.c._get('/feed/speeddial'); }

  // Write operations (require write:statuses scope)
  createPost(body: { status: string; visibility?: string; in_reply_to_id?: string; sensitive?: boolean; spoiler_text?: string }, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', '/statuses', { json: body, params: service ? { service } : undefined });
  }
  favourite(id: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', `/statuses/${encodeURIComponent(id)}/favourite`, { params: service ? { service } : undefined });
  }
  unfavourite(id: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', `/statuses/${encodeURIComponent(id)}/unfavourite`, { params: service ? { service } : undefined });
  }
  boost(id: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', `/statuses/${encodeURIComponent(id)}/reblog`, { params: service ? { service } : undefined });
  }
  unboost(id: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', `/statuses/${encodeURIComponent(id)}/unreblog`, { params: service ? { service } : undefined });
  }
  bookmark(id: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', `/statuses/${encodeURIComponent(id)}/bookmark`, { params: service ? { service } : undefined });
  }
  unbookmark(id: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', `/statuses/${encodeURIComponent(id)}/unbookmark`, { params: service ? { service } : undefined });
  }
  deletePost(id: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('DELETE', `/statuses/${encodeURIComponent(id)}`, { params: service ? { service } : undefined });
  }
}

// ==========================================================================
// Search
// ==========================================================================

/** Search across feeds, posts, accounts, and podcasts. */
class SearchAPI {
  constructor(private c: SurfClient) {}

  search(q: string, type: 'feeds' | 'posts' | 'accounts' | 'podcasts' | 'rss' = 'feeds', limit = 20) {
    return this.c._get('/search', { q, type, limit });
  }
  feeds(q: string, limit = 20) { return this.search(q, 'feeds', limit); }
  posts(q: string, limit = 20) { return this.search(q, 'posts', limit); }
  accounts(q: string, limit = 20) { return this.search(q, 'accounts', limit); }
  podcasts(q: string, limit = 20) { return this.search(q, 'podcasts', limit); }
  discover(type: 'recommended' | 'similar' | 'interests' = 'recommended', opts?: { surf_id?: string; limit?: number }) {
    return this.c._get('/search/discover', { type, ...opts });
  }
}

// ==========================================================================
// AI (use:ai scope, 10/day)
// ==========================================================================

/** AI-powered features: natural language search, feed summaries, feed builder. */
class AIAPI {
  constructor(private c: SurfClient) {}

  ask(query: string, opts?: { k?: number; schemaType?: string; feedId?: string }) {
    return this.c._get('/ai/ask', { query, k: opts?.k, schema_type: opts?.schemaType, feed_id: opts?.feedId });
  }
  feedSummary(surf_id: string, limit = 20) {
    return this.c._get('/ai/feed-summary', { surf_id, limit });
  }
  threadSummary(post_at: string) {
    return this.c._get('/ai/thread-summary', { post_at });
  }
  /** Fact-check a claim, paragraph, or post. Provide exactly one of `text` or `postSurfId`. */
  factCheck(opts: { text?: string; postSurfId?: string; feedId?: string }) {
    const body: Record<string, string> = {};
    if (opts.text !== undefined) body.text = opts.text;
    if (opts.postSurfId !== undefined) body.postSurfId = opts.postSurfId;
    if (opts.feedId !== undefined) body.feedId = opts.feedId;
    return this.c._post('/ai/fact-check', body);
  }
  async *buildFeed(prompt: string, feed_id?: string): AsyncGenerator<string> {
    const resp = await this.c._request<Response>('POST', '/ai/feed-builder', {
      json: { prompt, feed_id },
      raw: true,
    });
    const reader = resp.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      for (const line of text.split('\n')) {
        if (line.trim()) yield line;
      }
    }
  }
}

// ==========================================================================
// Account
// ==========================================================================

/** Account lookup and profile management. */
class AccountAPI {
  constructor(private c: SurfClient) {}

  get() { return this.c._get('/account'); }
  update(fields: Record<string, unknown>) { return this.c._put('/account', fields); }
  lookup(account: string) { return this.c._get('/account/lookup', { account }); }
  getLinks(): Promise<ProfileLink[]> { return this.c._get<ProfileLink[]>('/account/links'); }
  addLink(link: Omit<ProfileLink, 'id'>) { return this.c._post('/account/links', link); }
  updateLink(id: string, link: Partial<ProfileLink>) { return this.c._put(`/account/links/${id}`, { id, ...link }); }
  deleteLink(id: string) { return this.c._delete(`/account/links/${id}`); }
  follow(accountId: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', `/accounts/${accountId}/follow`, { params: service ? { service } : undefined });
  }
  unfollow(accountId: string, service?: 'bluesky' | 'mastodon') {
    return this.c._request('POST', `/accounts/${accountId}/unfollow`, { params: service ? { service } : undefined });
  }
  getConnectedApps(): Promise<ConnectedApp[]> { return this.c._get('/account/connected-apps'); }
  revokeConnectedApp(authorizationId: number) { return this.c._post(`/account/connected-apps/${authorizationId}/revoke`); }
}

// ==========================================================================
// Content
// ==========================================================================

/** URL resolution, article extraction, and language detection. */
class ContentAPI {
  constructor(private c: SurfClient) {}

  resolve(url: string): Promise<ResolveResult> { return this.c._get('/content/resolve', { url }); }
  extract(url: string, type: 'article' | 'image' | 'video' | 'audio' = 'article') {
    return this.c._get('/content/extract', { url, type });
  }
  language(url: string) { return this.c._get('/content/language', { url }); }
  topics(url: string): Promise<TopicsResult> { return this.c._get('/content/topics', { url }); }
  enrich(postId: string): Promise<EnrichmentData> { return this.c._get('/content/enrich', { postId }); }
}

// ==========================================================================
// Images
// ==========================================================================

/** AI-powered image analysis. */
class ImagesAPI {
  constructor(private c: SurfClient) {}

  info(url: string) { return this.c._get('/image/info', { url }); }
  async resize(url: string, size: 'small' | 'medium' | 'large' | 'xlarge' = 'medium'): Promise<ArrayBuffer> {
    const resp = await this.c._request<Response>('GET', '/image/resize', { params: { url, size }, raw: true });
    return resp.arrayBuffer();
  }
  async colors(url: string, k = 5): Promise<ArrayBuffer> {
    const resp = await this.c._request<Response>('GET', '/image/colors', { params: { url, k }, raw: true });
    return resp.arrayBuffer();
  }
  moderate(url: string): Promise<ModerationResult> { return this.c._get('/image/moderate', { url }); }
}

// ==========================================================================
// Audio
// ==========================================================================

/** Radio stations, briefings, podcasts, and text-to-speech. */
class AudioAPI {
  constructor(private c: SurfClient) {}

  listStations() { return this.c._get('/audio/radio/stations'); }
  getStation(id: string) { return this.c._get(`/audio/radio/stations/${id}`); }
  createStation(feed_surf_id: string, title?: string) {
    return this.c._post('/audio/radio/stations', { feed_surf_id, title });
  }
  generateProgram(stationId: string) { return this.c._post(`/audio/radio/stations/${stationId}/generate`); }
  getProgram(programId: string) { return this.c._get(`/audio/radio/programs/${programId}`); }
  generateBriefing() { return this.c._post('/audio/briefing/generate'); }
  getBriefing(id?: string) { return this.c._get(id ? `/audio/briefing/${id}` : '/audio/briefing/latest'); }
  getTranscript(episode_url: string) { return this.c._get('/audio/transcript', { episode_url }); }
  getDailyQuiz() { return this.c._get('/audio/quiz/daily'); }
  async textToSpeech(text: string, voice = 'en-US-AriaNeural'): Promise<ArrayBuffer> {
    const resp = await this.c._request<Response>('POST', '/audio/tts', { json: { text, voice }, raw: true });
    return resp.arrayBuffer();
  }
}

// ==========================================================================
// Notifications
// ==========================================================================

/** Notification feed and badge management. */
class NotificationsAPI {
  constructor(private c: SurfClient) {}

  list(opts?: { limit?: number; cursor?: string; type?: string }) {
    return this.c._get('/notifications', opts);
  }
  markRead() { return this.c._post('/notifications/read'); }
}

// ==========================================================================
// Preferences
// ==========================================================================

/** User preference management. */
class PreferencesAPI {
  constructor(private c: SurfClient) {}

  get() { return this.c._get('/preferences/account'); }
  update(prefs: Record<string, unknown>) { return this.c._patch('/preferences/account', prefs); }
}

// ==========================================================================
// Custom Feeds
// ==========================================================================

/**
 * Feed theme configuration using semantic color names.
 *
 * Separates header/image concerns from color concerns. Color names describe
 * purpose (`surface`, `surfaceCard`) rather than components (`feedBackground`,
 * `postBackground`), so they survive client redesigns.
 *
 * @example
 * ```ts
 * const theme: FeedTheme = {
 *   header: {
 *     image: 'https://cdn.example.com/logo.png',
 *     imageSize: { width: 600, height: 272 },
 *   },
 *   colors: {
 *     light: { surface: '#EFEADD', surfaceHeader: '#005F5F' },
 *   },
 * };
 * client.customFeeds.create({ title: 'My Feed', theme });
 * ```
 */
export interface FeedTheme {
  header?: {
    image?: string;
    imageDark?: string;
    imageSize?: { width: number; height: number };
    imagePadding?: { top?: number; bottom?: number };
    layout?: 'banner' | 'compact' | 'minimal';
    responsive?: {
      compact?: {
        imageSize?: { width: number; height: number };
        imagePadding?: { top?: number; bottom?: number };
      };
    };
  };
  colors?: {
    light?: FeedThemeColorPalette;
    dark?: FeedThemeColorPalette;
  };
}

export interface FeedThemeColorPalette {
  surface?: string;
  surfaceHeader?: string;
  surfaceCard?: string;
  onSurface?: string;
  onHeader?: string;
  accent?: string;
  [key: string]: string | undefined;
}

/**
 * Writable shape for a custom-feed operator — the fields the API accepts on create.
 * Server-assigned fields (`id`, `created`, `last_modified`) live on the response object.
 *
 * Common case:
 * ```ts
 * { surfId: 'surf/topic/artificial-intelligence', operator: 'source' }
 * ```
 */
export interface FeedOperator {
  surfId: string;
  /** Defaults to `'source'` when omitted. */
  operator?: 'source' | 'include' | 'filtering_include' | 'exclude' | 'score' | (string & {});
  filters?: Array<{ surfId: string; operator?: 'source' | 'include' | 'filtering_include' | 'exclude' | 'score' | (string & {}) }>;
}

/** Custom feed CRUD and operator management. */
class CustomFeedsAPI {
  constructor(private c: SurfClient) {}

  list() { return this.c._get('/custom'); }
  get(feedId: string) { return this.c._get(`/custom/${feedId}`); }
  create(body: { title: string; description?: string; operators?: unknown[]; image?: string; theme?: FeedTheme }) {
    const { theme, ...rest } = body;
    const payload: Record<string, unknown> = { ...rest };
    if (theme) payload.theme = theme;
    return this.c._post('/custom', payload);
  }

  /**
   * Create a new custom feed with typed {@link FeedOperator} objects.
   *
   * ```ts
   * client.customFeeds.createWithOperators('AI News', [
   *   { surfId: 'surf/topic/artificial-intelligence', operator: 'source' },
   *   { surfId: 'surf/hashtag/machinelearning', operator: 'source' },
   * ], 'Latest AI');
   * ```
   */
  createWithOperators(title: string, operators: FeedOperator[], description?: string) {
    return this.create({ title, description, operators });
  }
  update(feedId: string, body: Record<string, unknown> & { theme?: FeedTheme }) {
    const { theme, ...rest } = body;
    const payload: Record<string, unknown> = { ...rest };
    if (theme) payload.theme = theme;
    return this.c._put(`/custom/${feedId}`, payload);
  }
  delete(feedId: string) { return this.c._delete(`/custom/${feedId}`); }
  clone(feedId: string) { return this.c._post(`/custom/${feedId}/clone`); }
  publish(feedId: string) { return this.c._post(`/custom/${feedId}/publish`); }
  unpublish(feedId: string) { return this.c._post(`/custom/${feedId}/unpublish`); }
  addOperator(feedId: string, op: Record<string, unknown>) { return this.c._post(`/custom/${feedId}/operators`, [op]); }
  addOperators(feedId: string, ops: Record<string, unknown>[]) { return this.c._post(`/custom/${feedId}/operators`, ops); }
  updateOperator(feedId: string, opId: string, op: Record<string, unknown>) {
    return this.c._put(`/custom/${feedId}/operators/${opId}`, op);
  }
  removeOperator(feedId: string, opId: string) { return this.c._delete(`/custom/${feedId}/operators/${opId}`); }
}

// ==========================================================================
// Media
// ==========================================================================

/** Media upload for posts. */
class MediaAPI {
  constructor(private c: SurfClient) {}

  async upload(file: Blob | File, filename = 'image.jpg'): Promise<any> {
    const form = new FormData();
    form.append('file', file, filename);
    const url = `${(this.c as any).baseUrl}${API_PREFIX}/media/upload`;
    const resp = await ((this.c as any)._fetch as typeof fetch)(url, {
      method: 'POST',
      headers: { 'X-API-Key': (this.c as any).apiKey },
      body: form,
    });
    if (!resp.ok) throw new SurfAPIError(resp.statusText, resp.status);
    return resp.json();
  }

  /**
   * Start AI generation of a feed cover image (Stable Diffusion XL). Requires the
   * `use:ai` scope. Async submit/poll: returns immediately with `{ key, url, status:
   * 'pending' }` — generation runs server-side (can take a couple minutes). Poll
   * {@link getGenerateImageStatus} with `key` until `done`, then use `url`. Or call
   * {@link generateImageAndWait} to do both. `skipRefiner` trades quality for speed.
   */
  generateImage(
    prompt: string,
    opts?: { skipRefiner?: boolean },
  ): Promise<{ key: string; url: string; status: string }> {
    return this.c._post('/media/generate-image', { prompt, skipRefiner: opts?.skipRefiner ?? false });
  }

  /** Poll a generation job: `{ status: 'pending' | 'done' | 'failed' | 'not_found' }`. */
  getGenerateImageStatus(key: string): Promise<{ status: string }> {
    return this.c._get('/media/generate-image/status', { key });
  }

  /**
   * Submit a generation job and poll until it completes, returning the image URL.
   * Polls every `pollIntervalMs` (default 4s) up to `timeoutMs` (default 10 min).
   * Throws {@link SurfAPIError} if generation fails or times out.
   */
  async generateImageAndWait(
    prompt: string,
    opts?: { skipRefiner?: boolean; pollIntervalMs?: number; timeoutMs?: number },
  ): Promise<{ url: string }> {
    const submit = await this.generateImage(prompt, { skipRefiner: opts?.skipRefiner });
    const intervalMs = opts?.pollIntervalMs ?? 4000;
    const deadline = Date.now() + (opts?.timeoutMs ?? 10 * 60 * 1000);
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, intervalMs));
      const { status } = await this.getGenerateImageStatus(submit.key);
      if (status === 'done') return { url: submit.url };
      if (status === 'failed' || status === 'not_found') {
        throw new SurfAPIError(`Image generation ${status}`, 502);
      }
    }
    throw new SurfAPIError('Image generation timed out', 504);
  }
}

// ==========================================================================
// Diagnostics
// ==========================================================================

/**
 * Self-service diagnostics and confidential debug-bundle sharing.
 *
 * Lets your agent ask "what's wrong with my integration?" and, when handing a
 * problem to Surf's support agent, share a redacted, short-lived snapshot of
 * the diagnosis without exposing a credential.
 *
 * @example
 * ```ts
 * const diag = await client.diagnostics.diagnose();   // this token's own app
 * for (const f of diag.findings) {
 *   console.log(f.severity, f.title, '->', f.recommendation);
 * }
 * const bundle = await client.diagnostics.createBundle({ ttlMinutes: 15 });
 * console.log('Share with Surf support:', bundle.share_url);
 * ```
 */
class DiagnosticsAPI {
  constructor(private c: SurfClient) {}

  /**
   * Structured diagnosis (findings + token health + usage + errors).
   * With an app API key, omit `appId` to diagnose that token's own app.
   */
  diagnose(appId?: string): Promise<any> {
    return this.c._dpGet(appId ? `/applications/${encodeURIComponent(appId)}/diagnose` : '/diagnose');
  }

  /** Mint a redacted, expiring debug bundle. Returns share_token + share_url. */
  createBundle(opts?: { appId?: string; ttlMinutes?: number }): Promise<any> {
    const path = opts?.appId ? `/applications/${encodeURIComponent(opts.appId)}/debug-bundle` : '/debug-bundle';
    return this.c._dpPost(path, { ttl_minutes: opts?.ttlMinutes ?? 15 });
  }

  /** Fetch a shared bundle by its share token (no auth required). */
  getBundle(token: string): Promise<any> {
    return this.c._dpGet(`/debug-bundle/${encodeURIComponent(token)}`);
  }

  /** Revoke a bundle you minted before it expires. */
  revokeBundle(token: string): Promise<any> {
    return this.c._dpDelete(`/debug-bundle/${encodeURIComponent(token)}`);
  }
}

// ==========================================================================
// RTB Client
// ==========================================================================

export interface SurfRTBClientOptions {
  /** API key with rtb:* scopes (same surf_sk_live_... key as SurfClient) */
  apiKey: string;
  /** Base URL (default: https://surf.social) */
  baseUrl?: string;
  /** Request timeout in ms (default: 30_000) */
  timeout?: number;
  /**
   * Max automatic retries on 429 / 5xx / network errors (default: 3).
   * Matches SurfClient: capped exponential backoff, respects Retry-After.
   */
  maxRetries?: number;
  /** Custom fetch implementation */
  fetch?: typeof globalThis.fetch;
}

export interface RTBBidRequest {
  id: string;
  imp: Array<{
    id: string;
    banner?: { w: number; h: number; pos?: number; btype?: number[]; battr?: number[] };
    video?: { mimes: string[]; minduration?: number; maxduration?: number; w?: number; h?: number };
    native?: { request: string; ver?: string };
    audio?: Record<string, unknown>;
    bidfloor?: number;
    bidfloorcur?: string;
    ext?: { surf?: { feed_id?: string; feed_ids?: string[] } };
  }>;
  site?: { id?: string; domain?: string; page?: string; cat?: string[]; keywords?: string };
  device?: Record<string, unknown>;
  user?: { id?: string };
  test?: number;
  at?: number;
  tmax?: number;
  cur?: string[];
}

/**
 * Surf RTB (Real-Time Bidding) Client.
 *
 * Uses the same `surf_sk_live_...` API key as {@link SurfClient} via `X-API-Key`
 * header, but targets the RTB endpoints at `/devportal/v1/rtb/*`.
 * The API key must include the `rtb:bid` and/or `rtb:reports` scopes.
 *
 * @example
 * ```ts
 * const rtb = new SurfRTBClient({ apiKey: 'surf_sk_live_...' });
 *
 * // Sandbox mode -- synthetic bids, no real spend
 * const response = await rtb.bid({
 *   id: 'req-1',
 *   imp: [{ id: '1', banner: { w: 300, h: 250 } }],
 * }, true);
 *
 * // Impression/click/win/billing fire from the tracker URLs in the bid
 * // response (bid.nurl / bid.burl and the adm trackers) — no separate call.
 * ```
 */
export class SurfRTBClient {
  private baseUrl: string;
  private apiKey: string;
  private timeout: number;
  private maxRetries: number;
  private _fetch: typeof globalThis.fetch;

  constructor(options: SurfRTBClientOptions) {
    this.baseUrl = (options.baseUrl ?? 'https://surf.social').replace(/\/+$/, '');
    this.apiKey = options.apiKey;
    this.timeout = options.timeout ?? 30_000;
    const r = options.maxRetries ?? 3;
    this.maxRetries = Number.isFinite(r) ? Math.max(0, Math.floor(r)) : 3;
    this._fetch = options.fetch ?? globalThis.fetch;
  }

  private url(path: string): string {
    return `${this.baseUrl}/devportal/v1/rtb${path}`;
  }

  private async request(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<any> {
    const url = new URL(this.url(path));
    if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    const headers: Record<string, string> = {
      'X-API-Key': this.apiKey,
      'User-Agent': 'surf-api-ts/1.0.0',
      'Accept': 'application/json',
    };
    // Only advertise a JSON body Content-Type when there actually is one
    // (GETs have none) — matches SurfClient.
    if (body !== undefined && body !== null) headers['Content-Type'] = 'application/json';
    const reqBody = body !== undefined && body !== null ? JSON.stringify(body) : undefined;

    const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));
    let lastErr: unknown;

    // Retry on 429 (respecting Retry-After) and 5xx with capped exponential
    // backoff — mirrors SurfClient._request exactly.
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      let fetchSucceeded = false;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeout);
      try {
        const resp = await this._fetch(url.toString(), {
          method,
          headers,
          body: reqBody,
          signal: controller.signal,
        });

        if (resp.status === 429 && attempt < this.maxRetries) {
          clearTimeout(timer);
          const raw = parseInt(resp.headers.get('Retry-After') ?? '');
          const retryAfter = Math.min(Number.isFinite(raw) && raw > 0 ? raw : Math.pow(2, attempt), 60);
          try { await resp.body?.cancel(); } catch {}
          await sleep(retryAfter * 1_000);
          continue;
        }

        if (resp.status >= 500 && attempt < this.maxRetries) {
          clearTimeout(timer);
          try { await resp.body?.cancel(); } catch {}
          await sleep(Math.min(Math.pow(2, attempt), 60) * 1_000);
          continue;
        }

        if (resp.status === 401) throw new SurfAuthError('RTB auth failed (401). Check your API key.');
        if (resp.status === 403) throw new SurfScopeError('RTB forbidden (403). API key may lack required rtb:* scope.');
        if (resp.status === 429) {
          const raw = parseInt(resp.headers.get('Retry-After') ?? '');
          throw new SurfRateLimitError('Rate limited (429)', Number.isFinite(raw) && raw > 0 ? raw : 5);
        }
        if (!resp.ok) {
          const text = await resp.text().catch(() => '');
          throw new SurfAPIError(text || `HTTP ${resp.status}`, resp.status);
        }
        // Tag successful-fetch scope: errors below (e.g. JSON parse) must not be retried.
        fetchSucceeded = true;
        // A 204 or empty body (e.g. sandbox no-bid) has no JSON to parse —
        // return {} instead of throwing. Mirrors SurfClient._request.
        if (resp.status === 204) return {};
        const text = await resp.text();
        if (!text) return {};
        return JSON.parse(text);
      } catch (e) {
        if (e instanceof SurfAPIError) throw e;
        if (fetchSucceeded) throw e;
        lastErr = e;
        if (attempt < this.maxRetries) {
          clearTimeout(timer);
          await sleep(Math.min(Math.pow(2, attempt), 60) * 1_000);
        }
      } finally {
        clearTimeout(timer);
      }
    }
    throw lastErr ?? new SurfAPIError('Request failed', 0, 'connection_error');
  }

  /** Send an OpenRTB 2.5 bid request. */
  async bid(request: RTBBidRequest, sandbox = false): Promise<any> {
    const body = sandbox ? { ...request, test: 1 } : request;
    return this.request('POST', '/bid', body);
  }

  /** Get RTB performance reports. */
  async reports(days = 30, granularity: 'hour' | 'day' = 'day', appId?: number): Promise<any> {
    const params: Record<string, string> = { days: String(days), granularity };
    if (appId != null) params.app_id = String(appId);
    return this.request('GET', '/reports', undefined, params);
  }

  /** Get RTB configuration and tier info. */
  async config(appId?: number): Promise<any> {
    const params: Record<string, string> = {};
    if (appId != null) params.app_id = String(appId);
    return this.request('GET', '/config', undefined, params);
  }

  /** List available RTB scopes. */
  async scopes(): Promise<any[]> {
    const data = await this.request('GET', '/scopes');
    return data.scopes ?? [];
  }

  /**
   * Get your personalized ads.txt entry for authorizing Surf as a seller.
   * Add the returned `entries` to the ads.txt at the root of each domain
   * where you display Surf ads.
   */
  async adsTxt(appId?: number): Promise<any> {
    const params: Record<string, string> = {};
    if (appId != null) params.app_id = String(appId);
    return this.request('GET', '/ads-txt', undefined, params);
  }
}
