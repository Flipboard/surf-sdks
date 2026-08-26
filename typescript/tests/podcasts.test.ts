/**
 * Unit tests for the podcast intelligence audio methods — no live API required.
 *
 * Verifies the paths and query params for episode/guest search, mentions,
 * sponsors, and show notes; undefined params omitted; the sponsors
 * company-or-episode requirement; `episode_url` convenience hashing; and the
 * pure-TS SHA-1 helper against known vectors. Uses an injected mock `fetch`.
 */
import { test } from 'node:test';
import assert from 'node:assert';
import { createHash } from 'node:crypto';

import { SurfClient, episodeUrlHash } from '../src/index';

const BASE = 'https://api.surf.social/v1';
const EPISODE_URL = 'https://cdn.example.com/podcasts/ep-142.mp3';
const EPISODE_URL_HASH = createHash('sha1').update(EPISODE_URL).digest('hex');
const FLYF_ID = 'd7e340ff6462708b5519d65d3faab82ecb6c4c37';

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

test('searchPodcastEpisodes hits /audio/episodes/search with q only by default', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.searchPodcastEpisodes('ai agents');
  assert.equal(calls[0].method, 'GET');
  assert.equal(calls[0].url, `${BASE}/audio/episodes/search?q=ai+agents`);
});

test('searchPodcastEpisodes passes flyf_id and limit', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.searchPodcastEpisodes('ai', { flyf_id: FLYF_ID, limit: 5 });
  const u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/episodes/search');
  assert.equal(u.searchParams.get('q'), 'ai');
  assert.equal(u.searchParams.get('flyf_id'), FLYF_ID);
  assert.equal(u.searchParams.get('limit'), '5');
});

test('searchPodcastGuests hits /audio/guests/search with default limit 20', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.searchPodcastGuests('Sam Altman');
  assert.equal(calls[0].url, `${BASE}/audio/guests/search?q=Sam+Altman&limit=20`);
});

test('getPodcastMentions passes entity and optional filters', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.audio.getPodcastMentions('Anthropic');
  assert.equal(calls[0].url, `${BASE}/audio/mentions?entity=Anthropic`);

  await c.audio.getPodcastMentions('Anthropic', {
    entity_type: 'organization', flyf_id: FLYF_ID, limit: 50, offset: 100,
  });
  const u = new URL(calls[1].url);
  assert.equal(u.pathname, '/v1/audio/mentions');
  assert.equal(u.searchParams.get('entity_type'), 'organization');
  assert.equal(u.searchParams.get('flyf_id'), FLYF_ID);
  assert.equal(u.searchParams.get('limit'), '50');
  assert.equal(u.searchParams.get('offset'), '100');
});

test('getPodcastSponsors by company', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.getPodcastSponsors({ company: 'Squarespace' });
  assert.equal(calls[0].url, `${BASE}/audio/sponsors?company=Squarespace`);
});

test('getPodcastSponsors hashes episode_url into episode_url_hash', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.getPodcastSponsors({ episode_url: EPISODE_URL });
  const u = new URL(calls[0].url);
  assert.equal(u.searchParams.get('episode_url_hash'), EPISODE_URL_HASH);
  assert.equal(u.searchParams.get('episode_url'), null, 'raw episode_url is not sent');
});

test('getPodcastSponsors prefers an explicit episode_url_hash over episode_url', async () => {
  const calls: Call[] = [];
  const explicit = 'a'.repeat(40);
  await clientWithCapture(calls).audio.getPodcastSponsors({
    episode_url_hash: explicit, episode_url: EPISODE_URL,
  });
  const u = new URL(calls[0].url);
  assert.equal(u.searchParams.get('episode_url_hash'), explicit);
});

test('getPodcastSponsors throws when neither company nor an episode is given', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  assert.throws(() => c.audio.getPodcastSponsors({}), /company/);
  assert.equal(calls.length, 0, 'no request is made');
});

test('getShowNotes hits /audio/transcripts/show-notes and forwards language', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.audio.getShowNotes(EPISODE_URL);
  const u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/transcripts/show-notes');
  assert.equal(u.searchParams.get('episode_url'), EPISODE_URL);
  assert.equal(u.searchParams.get('language'), null, 'language omitted when undefined');

  await c.audio.getShowNotes(EPISODE_URL, 'es');
  assert.equal(new URL(calls[1].url).searchParams.get('language'), 'es');
});

test('episodeUrlHash matches node:crypto SHA-1 on known vectors', () => {
  assert.equal(episodeUrlHash('abc'), 'a9993e364706816aba3e25717850c26c9cd0d89d');
  assert.equal(episodeUrlHash(''), 'da39a3ee5e6b4b0d3255bfef95601890afd80709');
  assert.equal(episodeUrlHash(EPISODE_URL), EPISODE_URL_HASH);
  // Multi-byte UTF-8 and >64-byte (multi-block) inputs.
  for (const s of ['pöd/cast—épisode ✓', 'x'.repeat(55), 'y'.repeat(64), 'z'.repeat(200)]) {
    assert.equal(episodeUrlHash(s), createHash('sha1').update(s, 'utf8').digest('hex'), s.slice(0, 12));
  }
});

// --------------------------------------------------------------------------
// Phase 4 — fact checks, translations, catch-up, skip-to-topic
// --------------------------------------------------------------------------

test('getFactChecks hits /audio/fact-checks with the episode URL', async () => {
  const calls: Call[] = [];
  await clientWithCapture(calls).audio.getFactChecks(EPISODE_URL);
  assert.equal(calls[0].method, 'GET');
  const u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/fact-checks');
  assert.equal(u.searchParams.get('episode_url'), EPISODE_URL);
});

test('getTranslation passes episode_url and language', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.audio.getTranslation(EPISODE_URL, 'es');
  let u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/translations');
  assert.equal(u.searchParams.get('episode_url'), EPISODE_URL);
  assert.equal(u.searchParams.get('language'), 'es');

  // Regional codes go through verbatim
  await c.audio.getTranslation(EPISODE_URL, 'pt-BR');
  u = new URL(calls[1].url);
  assert.equal(u.searchParams.get('language'), 'pt-BR');
});

test('getCatchUp passes the playback position as timestamp', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.audio.getCatchUp(EPISODE_URL, 1830.5);
  let u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/catch-up');
  assert.equal(u.searchParams.get('episode_url'), EPISODE_URL);
  assert.equal(u.searchParams.get('timestamp'), '1830.5');

  // 0 is a valid position and must not be dropped
  await c.audio.getCatchUp(EPISODE_URL, 0);
  u = new URL(calls[1].url);
  assert.equal(u.searchParams.get('timestamp'), '0');
});

test('skipToTopic defaults limit to 5 and forwards overrides', async () => {
  const calls: Call[] = [];
  const c = clientWithCapture(calls);
  await c.audio.skipToTopic(EPISODE_URL, 'the housing market');
  let u = new URL(calls[0].url);
  assert.equal(u.pathname, '/v1/audio/skip-to-topic');
  assert.equal(u.searchParams.get('episode_url'), EPISODE_URL);
  assert.equal(u.searchParams.get('topic'), 'the housing market');
  assert.equal(u.searchParams.get('limit'), '5');

  await c.audio.skipToTopic(EPISODE_URL, 'evals', 20);
  u = new URL(calls[1].url);
  assert.equal(u.searchParams.get('limit'), '20');
});
