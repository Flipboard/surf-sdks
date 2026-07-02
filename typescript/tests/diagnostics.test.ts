/**
 * Unit tests for the diagnostics namespace — no live API required.
 *
 * Verifies the SDK matches the py-services devportal contract: correct method,
 * the developer-portal host (not the /v1 data API), URL-escaped path segments,
 * the {ttl_minutes} body, and X-API-Key auth. Uses an injected mock `fetch`.
 */
import { test } from 'node:test';
import assert from 'node:assert';

import { SurfClient } from '../src/index';

const DEVPORTAL = 'https://surf.social/devportal/v1';

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

test('default + overridable devportal url; diagnose is self-scoped on the portal host', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.diagnostics.diagnose();
  assert.equal(calls[0].method, 'GET');
  assert.equal(calls[0].url, `${DEVPORTAL}/diagnose`);
  assert.equal(calls[0].headers['X-API-Key'], 'surf_sk_live_k');
});

test('diagnose escapes the app id path segment', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).diagnostics.diagnose('weird/id space');
  assert.equal(calls[0].url, `${DEVPORTAL}/applications/weird%2Fid%20space/diagnose`);
});

test('createBundle POSTs {ttl_minutes} to the app-scoped path', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).diagnostics.createBundle({ appId: 'app1', ttlMinutes: 5 });
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].url, `${DEVPORTAL}/applications/app1/debug-bundle`);
  assert.deepEqual(JSON.parse(calls[0].body as string), { ttl_minutes: 5 });
});

test('createBundle defaults ttl to 15 and works without an app id', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).diagnostics.createBundle();
  assert.equal(calls[0].url, `${DEVPORTAL}/debug-bundle`);
  assert.deepEqual(JSON.parse(calls[0].body as string), { ttl_minutes: 15 });
});

test('get/revoke bundle escape the token', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.diagnostics.getBundle('dbg_a/b');
  assert.equal(calls[0].method, 'GET');
  assert.equal(calls[0].url, `${DEVPORTAL}/debug-bundle/dbg_a%2Fb`);
  await c.diagnostics.revokeBundle('dbg_a/b');
  assert.equal(calls[1].method, 'DELETE');
  assert.equal(calls[1].url, `${DEVPORTAL}/debug-bundle/dbg_a%2Fb`);
});

test('devportalUrl is overridable', async () => {
  const calls: Call[] = [];
  const c = new SurfClient({
    apiKey: 'k',
    devportalUrl: 'https://devtest.surf.social/devportal/v1/',
    fetch: (async (url: any, opts: any) => {
      calls.push({ url: String(url), method: opts?.method, headers: opts?.headers ?? {} });
      return { ok: true, status: 200, headers: { get: () => null }, json: async () => ({}), body: { cancel: async () => {} } } as any;
    }) as unknown as typeof fetch,
  });
  await c.diagnostics.diagnose();
  assert.equal(calls[0].url, 'https://devtest.surf.social/devportal/v1/diagnose');
});
