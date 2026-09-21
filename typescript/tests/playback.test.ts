/**
 * Unit tests for the playback namespace — no live API required.
 *
 * Verifies the SDK matches the fldaily /playback contract: method, path, the
 * omission rules on the report body (an absent duration must not become 0, an
 * explicit `completed: false` must survive), repeated `post_id` params, and the
 * empty-list short circuit. Uses an injected mock `fetch`.
 */
import { test } from 'node:test';
import assert from 'node:assert';

import { SurfClient, PlaybackReport } from '../src/index';

const BASE = 'https://api.surf.social/v1';

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

test('report POSTs only the fields it was given', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls, [{ status: 204 }]);
  const report: PlaybackReport = { post_id: 'p1', feed_surf_id: 'surf/podcast/abc', position_ms: 125000 };
  await c.playback.report(report);
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].url, `${BASE}/playback`);
  // An omitted duration must be ABSENT, not 0: the server leaves a known duration
  // alone when a report omits it, and 0 would claim the episode has no length.
  assert.deepEqual(JSON.parse(calls[0].body as string), report);
});

test('report sends a zero position and an explicit completed:false', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls, [{ status: 204 }, { status: 204 }]);
  await c.playback.report({ post_id: 'p1', feed_surf_id: 'surf/podcast/abc', position_ms: 0 });
  assert.equal(JSON.parse(calls[0].body as string).position_ms, 0);
  // False is a statement, not an omission: it is how a client says "not finished".
  await c.playback.report({
    post_id: 'p1', feed_surf_id: 'surf/podcast/abc', position_ms: 1,
    duration_ms: 3600000, completed: false,
  });
  const second = JSON.parse(calls[1].body as string);
  assert.equal(second.completed, false);
  assert.equal(second.duration_ms, 3600000);
});

test('reportBatch wraps the items, in order', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls, [{ status: 204 }]);
  await c.playback.reportBatch([
    { post_id: 'p1', feed_surf_id: 'surf/podcast/abc', position_ms: 10 },
    { post_id: 'p2', feed_surf_id: 'surf/podcast/abc', position_ms: 20, completed: true },
  ]);
  assert.equal(calls[0].url, `${BASE}/playback/batch`);
  const items = JSON.parse(calls[0].body as string).items;
  assert.equal(items.length, 2);
  assert.equal(items[1].post_id, 'p2');
  assert.equal(items[1].completed, true);
});

test('recent sends the default limit, and an explicit one when given', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls, [{ json: [{ post_id: 'p1', position_ms: 5 }] }, { json: [] }]);
  const out = await c.playback.recent();
  assert.equal(calls[0].url, `${BASE}/playback?limit=50`);
  assert.equal(out[0].post_id, 'p1');
  await c.playback.recent({ limit: 10 });
  assert.equal(calls[1].url, `${BASE}/playback?limit=10`);
});

test('positions repeats post_id, and asks nothing when there is nothing to ask', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls, [{ json: [] }]);
  await c.playback.positions(['a', 'b']);
  assert.equal(calls[0].url, `${BASE}/playback/positions?post_id=a&post_id=b`);
  // A list screen with no ids should not cost a round trip, and an empty post_id
  // would be a 400 rather than an empty answer.
  assert.deepEqual(await c.playback.positions([]), []);
  assert.deepEqual(await c.playback.positions(['', '']), []);
  assert.equal(calls.length, 1);
});
