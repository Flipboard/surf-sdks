/**
 * Unit tests for the podcast popularity audio methods — no live API required.
 *
 * Verifies the paths and query params for the popular-shows and hot-episodes
 * charts, including the camelCase `ingestedOnly` wire param, boolean
 * serialization, defaults, and that `date` is omitted unless provided.
 * Uses an injected mock `fetch`.
 */
import { test } from 'node:test';
import assert from 'node:assert';

import { SurfClient } from '../src/index';

const BASE = 'https://api.surf.social/v1';

interface Call { url: string; method?: string; headers: Record<string, string>; body?: string }

function clientWithCapture(calls: Call[], apiKey = 'surf_sk_live_k') {
  const mockFetch = (async (url: any, opts: any) => {
    calls.push({ url: String(url), method: opts?.method, headers: opts?.headers ?? {}, body: opts?.body });
    return {
      ok: true,
      status: 200,
      statusText: 'OK',
      headers: { get: () => null },
      json: async () => ({}),
      body: { cancel: async () => {} },
    } as any;
  }) as unknown as typeof fetch;
  return new SurfClient({ apiKey, fetch: mockFetch });
}

test('getPopularShows hits /audio/popular/shows with server defaults', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.getPopularShows();
  assert.equal(calls[0].method, 'GET');
  const u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/popular/shows');
  assert.equal(u.searchParams.get('region'), 'us');
  assert.equal(u.searchParams.get('category'), 'all');
  assert.equal(u.searchParams.get('limit'), '50');
  assert.equal(u.searchParams.get('ingestedOnly'), 'true');
  assert.equal(u.searchParams.get('date'), null); // omitted for latest
});

test('getPopularShows passes region/category/limit/ingested_only/date', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.getPopularShows({
    region: 'gb', category: 'technology', limit: 10,
    ingested_only: false, date: '2026-08-30',
  });
  const u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/popular/shows');
  assert.equal(u.searchParams.get('region'), 'gb');
  assert.equal(u.searchParams.get('category'), 'technology');
  assert.equal(u.searchParams.get('limit'), '10');
  assert.equal(u.searchParams.get('ingestedOnly'), 'false');
  assert.equal(u.searchParams.get('date'), '2026-08-30');
});

test('getPopularEpisodes hits /audio/popular/episodes with default limit 50', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.getPopularEpisodes();
  assert.equal(calls[0].method, 'GET');
  assert.equal(calls[0].url, `${BASE}/audio/popular/episodes?limit=50`);
});

test('getPopularEpisodes passes limit and date', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.getPopularEpisodes({ limit: 5, date: '2026-08-30' });
  const u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/popular/episodes');
  assert.equal(u.searchParams.get('limit'), '5');
  assert.equal(u.searchParams.get('date'), '2026-08-30');
});

test('popularity calls carry the API key header', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.getPopularShows();
  assert.equal(calls[0].headers['X-API-Key'], 'surf_sk_live_k');
});
