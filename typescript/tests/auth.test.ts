/**
 * Unit tests for client authentication — no live API required.
 *
 * A client holds exactly one credential and sends exactly one header for it: an app key as
 * `X-API-Key`, an OAuth access token as `Authorization: Bearer`. The two are not
 * interchangeable, because `X-API-Key` validates its value as an app key and a JWT sent
 * there is simply not found. Uses an injected mock `fetch`.
 */
import { test } from 'node:test';
import assert from 'node:assert';

import { SurfClient } from '../src/index';

interface Call { headers: Record<string, string> }

function capture(calls: Call[], statuses: number[] = []) {
  let i = 0;
  return (async (_url: any, opts: any) => {
    calls.push({ headers: { ...(opts?.headers ?? {}) } });
    const status = statuses[i++] ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: 'OK',
      headers: { get: () => null },
      json: async () => ({}),
      text: async () => '{}',
      body: { cancel: async () => {} },
    } as any;
  }) as unknown as typeof fetch;
}

test('an app key is sent as X-API-Key and nothing else', async () => {
  const calls: Call[] = [];
  const client = new SurfClient({ apiKey: 'surf_sk_live_k', fetch: capture(calls) });
  await client.feeds.get('surf/topic/technology');
  assert.equal(calls[0].headers['X-API-Key'], 'surf_sk_live_k');
  assert.equal(calls[0].headers['Authorization'], undefined);
});

test('an access token is sent as a bearer and nothing else', async () => {
  const calls: Call[] = [];
  const client = new SurfClient({ accessToken: 'jwt-one', fetch: capture(calls) });
  await client.feeds.get('surf/topic/technology');
  assert.equal(calls[0].headers['Authorization'], 'Bearer jwt-one');
  assert.equal(calls[0].headers['X-API-Key'], undefined);
});

test('a refreshed token replaces the credential on the next request', async () => {
  const calls: Call[] = [];
  const client = new SurfClient({ accessToken: 'jwt-one', fetch: capture(calls) });
  await client.feeds.get('surf/topic/technology');
  client.accessToken = 'jwt-two';
  await client.feeds.get('surf/topic/technology');
  assert.equal(calls[0].headers['Authorization'], 'Bearer jwt-one');
  assert.equal(calls[1].headers['Authorization'], 'Bearer jwt-two');
});

test('a retry after a 429 picks up a token refreshed during the backoff', async () => {
  const calls: Call[] = [];
  const client = new SurfClient({
    accessToken: 'jwt-stale',
    maxRetries: 1,
    fetch: (async (url: any, opts: any) => {
      calls.push({ headers: { ...(opts?.headers ?? {}) } });
      if (calls.length === 1) {
        // Stand in for a refresh landing while the first attempt is backing off.
        client.accessToken = 'jwt-fresh';
        return {
          ok: false, status: 429, statusText: 'Too Many Requests',
          headers: { get: () => null }, json: async () => ({}), body: { cancel: async () => {} },
        } as any;
      }
      return {
        ok: true, status: 200, statusText: 'OK',
        headers: { get: () => null }, json: async () => ({}), body: { cancel: async () => {} },
      } as any;
    }) as unknown as typeof fetch,
  });
  await client.feeds.get('surf/topic/technology');
  assert.equal(calls[0].headers['Authorization'], 'Bearer jwt-stale');
  assert.equal(calls[1].headers['Authorization'], 'Bearer jwt-fresh',
    'a header captured before the retry loop would resend the replaced token');
});

test('the media methods authenticate the same way', async () => {
  const calls: Call[] = [];
  const client = new SurfClient({ accessToken: 'jwt-media', fetch: capture(calls) });
  await client.media.getAttachment('abc');
  assert.equal(calls[0].headers['Authorization'], 'Bearer jwt-media');
  assert.equal(calls[0].headers['X-API-Key'], undefined);
});

test('exactly one credential is required', () => {
  assert.throws(() => new SurfClient({ apiKey: 'k', accessToken: 't' }), /exactly one/);
  assert.throws(() => new SurfClient({} as any), /exactly one/);
  assert.throws(() => {
    const c = new SurfClient({ accessToken: 't' });
    c.accessToken = '';
  }, /cannot be empty/);
});
