/**
 * Unit tests for the sonars namespace — no live API required.
 *
 * Verifies the SDK matches the fldaily /sonars contract: method, path, query
 * params (undefined dropped), JSON bodies (incl. the explicit-null daily_cap on
 * PATCH), the `before` cursor walk, and 204 -> {} on delete. Uses an injected mock `fetch`.
 */
import { test } from 'node:test';
import assert from 'node:assert';

import { SurfClient } from '../src/index';

const BASE = 'https://api.surf.social/v1';
const SPEC = { subject: { hashtags: ['#opensearch'] }, surfaces: ['bluesky', 'mastodon'] };

interface Call { url: string; method?: string; body?: string }

function clientWithCapture(calls: Call[], responses: Array<{ status?: number; json?: unknown }> = []) {
  let i = 0;
  const mockFetch = (async (url: any, opts: any) => {
    calls.push({ url: String(url), method: opts?.method, body: opts?.body });
    const r = responses[i++] ?? {};
    const status = r.status ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: 'OK',
      headers: { get: () => null },
      json: async () => r.json ?? {},
      body: { cancel: async () => {} },
    } as any;
  }) as unknown as typeof fetch;
  return new SurfClient({ apiKey: 'surf_sk_live_k', fetch: mockFetch });
}

test('create POSTs name, spec and only the delivery fields given', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.sonars.create({ name: 'OpenSearch chatter', spec: SPEC });
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].url, `${BASE}/sonars`);
  assert.deepEqual(JSON.parse(calls[0].body as string), { name: 'OpenSearch chatter', spec: SPEC });
  await c.sonars.create({ name: 'n', spec: SPEC, enabled: false, cadence: 'instant', channels: [{ type: 'push' }], daily_cap: 20 });
  assert.deepEqual(JSON.parse(calls[1].body as string), {
    name: 'n', spec: SPEC, enabled: false, cadence: 'instant', channels: [{ type: 'push' }], daily_cap: 20,
  });
});

test('list / get / delete paths; ids are escaped as one segment; delete tolerates 204', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls, [{}, {}, {}, { status: 204 }]);
  await c.sonars.list();
  assert.equal(calls[0].method, 'GET');
  assert.equal(calls[0].url, `${BASE}/sonars`);
  await c.sonars.get('01j0ksyw6tgwfs0zmhhbc42kwa');
  assert.equal(calls[1].url, `${BASE}/sonars/01j0ksyw6tgwfs0zmhhbc42kwa`);
  await c.sonars.get('odd/id');
  assert.equal(calls[2].url, `${BASE}/sonars/odd%2Fid`);
  const out = await c.sonars.delete('abc');
  assert.equal(calls[3].method, 'DELETE');
  assert.equal(calls[3].url, `${BASE}/sonars/abc`);
  assert.deepEqual(out, {});
});

test('update PATCHes only the fields given and can clear daily_cap with an explicit null', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.sonars.update('abc', { name: 'renamed' });
  assert.equal(calls[0].method, 'PATCH');
  assert.equal(calls[0].url, `${BASE}/sonars/abc`);
  assert.deepEqual(JSON.parse(calls[0].body as string), { name: 'renamed' });
  await c.sonars.update('abc', { daily_cap: null, enabled: false });
  assert.deepEqual(JSON.parse(calls[1].body as string), { daily_cap: null, enabled: false });
});

test('matches drops absent params and passes before/limit', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.sonars.matches('abc');
  assert.equal(calls[0].url, `${BASE}/sonars/abc/matches`);
  await c.sonars.matches('abc', { before: 41, limit: 10 });
  assert.equal(calls[1].url, `${BASE}/sonars/abc/matches?before=41&limit=10`);
});

test('iterMatches follows next_before until it is null and honours a limit', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls, [
    { json: { matches: [{ id: 3, post_id: 'p3' }, { id: 2, post_id: 'p2' }], next_before: 2 } },
    { json: { matches: [{ id: 1, post_id: 'p1' }], next_before: null } },
  ]);
  const got: string[] = [];
  for await (const m of c.sonars.iterMatches('abc')) got.push(m.post_id);
  assert.deepEqual(got, ['p3', 'p2', 'p1']);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].url, `${BASE}/sonars/abc/matches?before=2`);

  const calls2: Call[] = [];
  const c2 = clientWithCapture(calls2, [{ json: { matches: [{ id: 3, post_id: 'p3' }, { id: 2, post_id: 'p2' }], next_before: 2 } }]);
  const first: string[] = [];
  for await (const m of c2.sonars.iterMatches('abc', { limit: 1 })) first.push(m.post_id);
  assert.deepEqual(first, ['p3']);
  assert.equal(calls2[0].url, `${BASE}/sonars/abc/matches?limit=1`);
});

test('preview POSTs the spec with days as a query param', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.sonars.preview(SPEC);
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].url, `${BASE}/sonars/preview`);
  assert.deepEqual(JSON.parse(calls[0].body as string), SPEC);
  await c.sonars.preview(SPEC, { days: 7 });
  assert.equal(calls[1].url, `${BASE}/sonars/preview?days=7`);
});
