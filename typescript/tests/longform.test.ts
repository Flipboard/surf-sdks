/**
 * Unit tests for the longform namespace — no live API required.
 *
 * Verifies AT-URIs are percent-encoded as a single path segment, the `format`
 * query param is omitted when undefined, `tags` repeats as multiple query
 * params, count/from paging params pass through, and the search.publications
 * helper hits /search/publications. Uses an injected mock `fetch`.
 */
import { test } from 'node:test';
import assert from 'node:assert';

import { SurfClient } from '../src/index';

const BASE = 'https://api.surf.social/v1';
const DOC_URI = 'at://did:plc:x/site.standard.document/3k2a';
const DOC_URI_ENC = encodeURIComponent(DOC_URI); // at%3A%2F%2Fdid%3Aplc%3Ax%2F...
const PUB_URI = 'at://did:plc:x/site.standard.publication/3pub';
const PUB_URI_ENC = encodeURIComponent(PUB_URI);

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

test('getDocument encodes the AT-URI as a single path segment and omits format by default', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.longform.getDocument(DOC_URI);
  assert.equal(calls[0].method, 'GET');
  assert.equal(calls[0].url, `${BASE}/documents/${DOC_URI_ENC}`);
  assert.ok(!calls[0].url.includes('?'), 'no query string when format is undefined');
  assert.equal(calls[0].headers['X-API-Key'], 'surf_sk_live_k');
});

test('getDocument passes format=blocks when requested', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).longform.getDocument(DOC_URI, { format: 'blocks' });
  assert.equal(calls[0].url, `${BASE}/documents/${DOC_URI_ENC}?format=blocks`);
});

test('getPublication encodes the AT-URI', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).longform.getPublication(PUB_URI);
  assert.equal(calls[0].method, 'GET');
  assert.equal(calls[0].url, `${BASE}/publications/${PUB_URI_ENC}`);
});

test('listDocuments repeats tags and passes count/from', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).longform.listDocuments(PUB_URI, { tags: ['a', 'b c'], count: 50, from: 10 });
  const url = new URL(calls[0].url);
  assert.equal(url.pathname, `/v1/publications/${PUB_URI_ENC}/documents`);
  assert.deepEqual(url.searchParams.getAll('tags'), ['a', 'b c']);
  assert.equal(url.searchParams.get('count'), '50');
  assert.equal(url.searchParams.get('from'), '10');
});

test('listDocuments without options sends no query params', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).longform.listDocuments(PUB_URI);
  assert.equal(calls[0].url, `${BASE}/publications/${PUB_URI_ENC}/documents`);
});

test('searchPublications sends q with optional count/from', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.longform.searchPublications('urbanism');
  assert.equal(calls[0].url, `${BASE}/search/publications?q=urbanism`);
  await c.longform.searchPublications('urbanism', { count: 5, from: 20 });
  assert.equal(calls[1].url, `${BASE}/search/publications?q=urbanism&count=5&from=20`);
});

test('search.publications helper hits /search/publications with default count', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.search.publications('city planning');
  assert.equal(calls[0].url, `${BASE}/search/publications?q=city+planning&count=20`);
  await c.search.publications('city', 10, { from: 30 });
  assert.equal(calls[1].url, `${BASE}/search/publications?q=city&count=10&from=30`);
});
