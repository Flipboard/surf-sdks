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
  ProfileLink,
  ModerationResult,
  EnrichmentData,
} from './types';

export * from './types';

const DEFAULT_BASE_URL = 'https://api.surf.social';
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
  private readonly timeout: number;
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

  constructor(options: SurfClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, '');
    this.timeout = options.timeout ?? 30_000;
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
  }

  /** @internal */
  async _request<T = any>(method: string, path: string, opts?: {
    params?: Record<string, string | number | boolean | undefined>;
    json?: unknown;
    raw?: boolean;
  }): Promise<T> {
    let url = `${this.baseUrl}${API_PREFIX}${path}`;
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
      'User-Agent': 'surf-api-ts/0.2.0',
    };
    let body: string | undefined;
    if (opts?.json !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(opts.json);
    }
    if (!opts?.raw) {
      headers['Accept'] = 'application/json';
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const resp = await this._fetch(url, {
        method,
        headers,
        body,
        signal: controller.signal,
      });

      this.rateLimit = {
        limit: parseInt(resp.headers.get('X-RateLimit-Limit') ?? '0'),
        remaining: parseInt(resp.headers.get('X-RateLimit-Remaining') ?? '0'),
        reset: resp.headers.get('X-RateLimit-Reset'),
      };

      if (!resp.ok) {
        let errBody: Partial<SurfErrorBody> = {};
        try { errBody = await resp.json(); } catch {}
        const msg = errBody.error_description ?? errBody.error ?? resp.statusText;
        if (resp.status === 401) throw new SurfAuthError(msg);
        if (resp.status === 403) throw new SurfScopeError(msg);
        if (resp.status === 404) throw new SurfNotFoundError(msg);
        if (resp.status === 429) {
          const retry = parseInt(resp.headers.get('Retry-After') ?? '60');
          throw new SurfRateLimitError(msg, retry);
        }
        throw new SurfAPIError(msg, resp.status, errBody.error);
      }

      if (opts?.raw) return resp as unknown as T;
      if (resp.status === 204) return {} as T;
      return await resp.json() as T;
    } finally {
      clearTimeout(timer);
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
}

// ==========================================================================
// Feeds
// ==========================================================================

class FeedsAPI {
  constructor(private c: SurfClient) {}

  get(surf_id: string) { return this.c._get('/feed', { surf_id }); }
  getPosts(surf_id: string, opts?: { limit?: number; cursor?: string; sort?: string }) {
    return this.c._get('/feed/posts', { surf_id, ...opts });
  }
  getPost(id: string, thread = false) {
    return this.c._get('/post', { id, thread: thread ? 'true' : undefined });
  }
  getFollowing(limit = 50) { return this.c._get('/feed/following', { limit }); }
  getSpeedDial() { return this.c._get('/feed/speeddial'); }

  // Write operations (require write:statuses scope)
  createPost(body: { status: string; visibility?: string; in_reply_to_id?: string; sensitive?: boolean; spoiler_text?: string }) {
    return this.c._post('/statuses', body);
  }
  favourite(id: string) { return this.c._post(`/statuses/${id}/favourite`); }
  unfavourite(id: string) { return this.c._post(`/statuses/${id}/unfavourite`); }
  boost(id: string) { return this.c._post(`/statuses/${id}/reblog`); }
  unboost(id: string) { return this.c._post(`/statuses/${id}/unreblog`); }
  bookmark(id: string) { return this.c._post(`/statuses/${id}/bookmark`); }
  deletePost(id: string) { return this.c._delete(`/statuses/${id}`); }
}

// ==========================================================================
// Search
// ==========================================================================

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

class AccountAPI {
  constructor(private c: SurfClient) {}

  get() { return this.c._get('/account'); }
  update(fields: Record<string, unknown>) { return this.c._put('/account', fields); }
  lookup(account: string) { return this.c._get('/account/lookup', { account }); }
  getLinks(): Promise<ProfileLink[]> { return this.c._get('/account/links'); }
  addLink(link: Omit<ProfileLink, 'id'>) { return this.c._post('/account/links', link); }
  updateLink(id: string, link: Partial<ProfileLink>) { return this.c._put(`/account/links/${id}`, { id, ...link }); }
  deleteLink(id: string) { return this.c._delete(`/account/links/${id}`); }
  follow(accountId: string) { return this.c._post(`/accounts/${accountId}/follow`); }
  unfollow(accountId: string) { return this.c._post(`/accounts/${accountId}/unfollow`); }
  getConnectedApps() { return this.c._get('/account/connected-apps'); }
  revokeConnectedApp(authorizationId: number) { return this.c._post(`/account/connected-apps/${authorizationId}/revoke`); }
}

// ==========================================================================
// Content
// ==========================================================================

class ContentAPI {
  constructor(private c: SurfClient) {}

  resolve(url: string) { return this.c._get('/content/resolve', { url }); }
  extract(url: string, type: 'article' | 'image' | 'video' | 'audio' = 'article') {
    return this.c._get('/content/extract', { url, type });
  }
  language(url: string) { return this.c._get('/content/language', { url }); }
  topics(url: string) { return this.c._get('/content/topics', { url }); }
  enrich(postId: string): Promise<EnrichmentData> { return this.c._get('/content/enrich', { postId }); }
}

// ==========================================================================
// Images
// ==========================================================================

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

class PreferencesAPI {
  constructor(private c: SurfClient) {}

  get() { return this.c._get('/preferences/account'); }
  update(prefs: Record<string, unknown>) { return this.c._patch('/preferences/account', prefs); }
}

// ==========================================================================
// Custom Feeds
// ==========================================================================

class CustomFeedsAPI {
  constructor(private c: SurfClient) {}

  list() { return this.c._get('/custom'); }
  get(feedId: string) { return this.c._get(`/custom/${feedId}`); }
  create(body: { title: string; description?: string; operators?: unknown[] }) {
    return this.c._post('/custom', body);
  }
  update(feedId: string, body: Record<string, unknown>) { return this.c._put(`/custom/${feedId}`, body); }
  delete(feedId: string) { return this.c._delete(`/custom/${feedId}`); }
  clone(feedId: string) { return this.c._post(`/custom/${feedId}/clone`); }
  publish(feedId: string) { return this.c._post(`/custom/${feedId}/publish`); }
  unpublish(feedId: string) { return this.c._post(`/custom/${feedId}/unpublish`); }
  addOperator(feedId: string, op: Record<string, unknown>) { return this.c._post(`/custom/${feedId}/operators`, op); }
  updateOperator(feedId: string, opId: string, op: Record<string, unknown>) {
    return this.c._put(`/custom/${feedId}/operators/${opId}`, op);
  }
  removeOperator(feedId: string, opId: string) { return this.c._delete(`/custom/${feedId}/operators/${opId}`); }
}

// ==========================================================================
// Media
// ==========================================================================

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
}
