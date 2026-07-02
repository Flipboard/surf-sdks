/**
 * Surf API TypeScript SDK Integration Tests
 *
 * Requires:
 *   SURF_API_TEST_TOKEN=surf_sk_live_...  (required)
 *   SURF_API_BASE_URL=https://api.surf.social  (optional)
 *
 * Run:
 *   npm run test:integration
 *
 * Tests are sequential: feeds -> search -> custom feeds -> write ops -> AI -> error handling.
 * Rate-limited (429) and server error (5xx) requests are retried automatically by the SDK.
 * Tests that require scopes the token lacks are skipped (401/403).
 */

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { SurfClient, SurfRTBClient, SurfAuthError, SurfScopeError, SurfNotFoundError, SurfAPIError } from '../src/index';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const API_TOKEN = process.env.SURF_API_TEST_TOKEN ?? '';
// The SDK adds /v1 internally, so strip it if the env var includes it
const BASE_URL = (process.env.SURF_API_BASE_URL ?? 'https://api.surf.social').replace(/\/v1\/?$/, '');

if (!API_TOKEN) {
  console.error('SURF_API_TEST_TOKEN is required. Skipping all tests.');
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Rate-limit-aware client wrapper
// ---------------------------------------------------------------------------

const client = new SurfClient({ apiKey: API_TOKEN, baseUrl: BASE_URL, timeout: 60_000 });

/** Returns true if err is a scope/auth issue we should skip on. */
function isScopeOrAuth(err: unknown): boolean {
  return err instanceof SurfAuthError || err instanceof SurfScopeError;
}

// ---------------------------------------------------------------------------
// 1. Feeds
// ---------------------------------------------------------------------------

describe('Feeds', { concurrency: false }, () => {
  it('should get feed metadata', async () => {
    const meta = await client.feeds.get('surf/topic/technology');
    assert.ok(meta, 'Should return feed metadata');
    assert.ok(meta.title, 'Feed should have a title');
  });

  it('should get posts with limit', async () => {
    const posts = await client.feeds.getPosts('surf/topic/technology', { limit: 5 });
    // Response may be array or object with posts key
    const items = Array.isArray(posts) ? posts : (posts as any).posts ?? (posts as any).items ?? [];
    assert.ok(items.length > 0, 'Should return at least one post');
    assert.ok(items.length <= 5, `Limit should be enforced, got ${items.length}`);
  });

  it('should paginate with cursor', async () => {
    const page1: any = await client.feeds.getPosts('surf/topic/technology', { limit: 2 });
    const items1 = Array.isArray(page1) ? page1 : page1.posts ?? page1.items ?? [];
    assert.ok(items1.length > 0, 'First page should have posts');

    // Look for cursor in response
    const cursor = page1?.cursor;
    if (!cursor) {
      console.log('  [skip] No cursor in response, pagination not testable');
      return;
    }

    const page2: any = await client.feeds.getPosts('surf/topic/technology', {
      limit: 2,
      cursor,
    });
    const items2 = Array.isArray(page2) ? page2 : page2.posts ?? page2.items ?? [];
    assert.ok(items2.length > 0, 'Second page should have posts');

    // Verify pages are different
    const ids1 = new Set(items1.map((p: any) => p.id));
    const ids2 = new Set(items2.map((p: any) => p.id));
    const overlap = [...ids2].filter((id) => ids1.has(id));
    assert.ok(overlap.length < items2.length, 'Pages should contain different posts');
  });
});

// ---------------------------------------------------------------------------
// 2. Search
// ---------------------------------------------------------------------------

describe('Search', { concurrency: false }, () => {
  it('should search feeds', async () => {
    const result = await client.search.feeds('technology', 5);
    assert.ok(result, 'Should return search results');
  });

  it('should search posts', async () => {
    const result = await client.search.posts('artificial intelligence', 5);
    assert.ok(result, 'Should return search results');
  });

  it('should search accounts', async () => {
    const result = await client.search.accounts('surf', 5);
    assert.ok(result, 'Should return search results');
  });

  it('should discover recommended feeds', async () => {
    const result = await client.search.discover('recommended');
    assert.ok(result, 'Should return discover results');
  });
});

// ---------------------------------------------------------------------------
// 3. Custom Feeds
// ---------------------------------------------------------------------------

describe('Custom Feeds', { concurrency: false }, () => {
  let feedId: string | null = null;
  let skipped = false;

  it('should create a custom feed', async () => {
    try {
      const result: any = await client.customFeeds.create({
        title: 'SDK Integration Test Feed',
        description: 'Automated test feed -- safe to delete',
      });
      const rawId: string = result?.id ?? result?.surfId ?? result?.surf_id ?? '';
      feedId = rawId.replace('surf/custom/', '');
      assert.ok(feedId, 'Should return a feed ID');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        skipped = true;
        console.log('  [skip] Token lacks write:feeds scope');
        return;
      }
      throw err;
    }
  });

  it('should add a topic operator', async () => {
    if (skipped || !feedId) return;
    const result = await client.customFeeds.addOperator(feedId, {
      surfId: 'surf/topic/technology',
      operator: 'source',
    });
    assert.ok(result !== undefined);
  });

  it('should add a hashtag operator', async () => {
    if (skipped || !feedId) return;
    const result = await client.customFeeds.addOperator(feedId, {
      surfId: 'surf/hashtag/opensource',
      operator: 'source',
    });
    assert.ok(result !== undefined);
  });

  it('should add a bluesky user operator', async () => {
    if (skipped || !feedId) return;
    const result = await client.customFeeds.addOperator(feedId, {
      surfId: 'bluesky/user/@jay.bsky.team',
      operator: 'source',
    });
    assert.ok(result !== undefined);
  });

  it('should get the feed and verify operators', async () => {
    if (skipped || !feedId) return;
    const feed: any = await client.customFeeds.get(feedId);
    assert.ok(feed, 'Should return the feed');
    const operators: any[] = feed.operators ?? [];
    const storedIds = new Set(operators.map((op: any) => op.surfId));
    assert.ok(
      storedIds.has('surf/topic/technology'),
      `Expected topic operator, got: ${JSON.stringify([...storedIds])}`,
    );
    assert.ok(
      storedIds.has('surf/hashtag/opensource'),
      `Expected hashtag operator, got: ${JSON.stringify([...storedIds])}`,
    );
    assert.ok(
      storedIds.has('bluesky/user/@jay.bsky.team'),
      `Expected bluesky user operator, got: ${JSON.stringify([...storedIds])}`,
    );
  });

  it('should fetch posts from the custom feed (may be empty)', async () => {
    if (skipped || !feedId) return;
    const posts = await client.feeds.getPosts(`surf/custom/${feedId}`, { limit: 5 });
    // New feeds may have no posts yet -- just verify no error
    assert.ok(posts !== undefined);
  });

  // Cleanup
  after(async () => {
    if (feedId) {
      try {
        await client.customFeeds.delete(feedId);
        console.log(`  [cleanup] Deleted custom feed ${feedId}`);
      } catch {
        console.log(`  [cleanup] Could not delete feed ${feedId} (may already be gone)`);
      }
    }
  });
});

// ---------------------------------------------------------------------------
// 3b. createWithOperators typed helper
// ---------------------------------------------------------------------------

describe('createWithOperators', { concurrency: false }, () => {
  let feedId: string | null = null;
  let skipped = false;

  it('should create a feed with typed FeedOperator objects', async () => {
    try {
      const result: any = await client.customFeeds.createWithOperators(
        'SDK OpTest Feed',
        [
          { surfId: 'surf/topic/technology', operator: 'source' },
          { surfId: 'surf/hashtag/opensource', operator: 'source' },
        ],
        'createWithOperators integration test -- safe to delete',
      );
      const rawId: string = result?.id ?? result?.surfId ?? result?.surf_id ?? '';
      feedId = rawId.replace('surf/custom/', '');
      assert.ok(feedId, 'Should return a feed ID');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        skipped = true;
        console.log('  [skip] Token lacks write:feeds scope');
        return;
      }
      throw err;
    }
  });

  it('should have the supplied operators stored on the feed', async () => {
    if (skipped || !feedId) return;
    const feed: any = await client.customFeeds.get(feedId);
    const storedIds = new Set((feed.operators ?? []).map((op: any) => op.surfId));
    assert.ok(storedIds.has('surf/topic/technology'), `topic operator missing, got: ${JSON.stringify([...storedIds])}`);
    assert.ok(storedIds.has('surf/hashtag/opensource'), `hashtag operator missing, got: ${JSON.stringify([...storedIds])}`);
  });

  after(async () => {
    if (feedId) {
      try {
        await client.customFeeds.delete(feedId);
        console.log(`  [cleanup] Deleted OpTest feed ${feedId}`);
      } catch {
        console.log(`  [cleanup] Could not delete OpTest feed ${feedId}`);
      }
    }
  });
});

// ---------------------------------------------------------------------------
// 3c. Custom Feed Themes
// ---------------------------------------------------------------------------

describe('Custom Feed Themes', { concurrency: false }, () => {
  let feedId: string | null = null;
  let skipped = false;

  it('should create a themed custom feed', async () => {
    try {
      const result: any = await client.customFeeds.create({
        title: 'SDK Theme Test Feed',
        description: 'Automated theme test -- safe to delete',
        theme: {
          header: {
            image: 'https://surf.social/img/surf-logo.png',
            imageSize: { width: 600, height: 272 },
          },
          colors: {
            light: { surface: '#EFEADD', surfaceHeader: '#005F5F' },
          },
        },
      });
      const rawId: string = result?.id ?? result?.surfId ?? '';
      feedId = rawId.replace('surf/custom/', '');
      assert.ok(feedId, 'Should return a feed ID');
      assert.ok(result.theme, 'Response should include theme');
      assert.strictEqual(result.theme.header?.image, 'https://surf.social/img/surf-logo.png');
      assert.strictEqual(result.theme.colors?.light?.surface, '#EFEADD');
      assert.strictEqual(result.theme.colors?.light?.surfaceHeader, '#005F5F');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        skipped = true;
        console.log('  [skip] Token lacks write:feeds scope');
        return;
      }
      throw err;
    }
  });

  it('should round-trip theme on GET', async () => {
    if (skipped || !feedId) return;
    const feed: any = await client.customFeeds.get(feedId);
    assert.ok(feed.theme, 'GET response should include theme');
    assert.strictEqual(feed.theme.header?.image, 'https://surf.social/img/surf-logo.png');
  });

  it('should update theme', async () => {
    if (skipped || !feedId) return;
    const result: any = await client.customFeeds.update(feedId, {
      title: 'SDK Theme Updated',
      theme: {
        header: {
          image: 'https://surf.social/img/surf-logo.png',
          imageSize: { width: 400, height: 200 },
        },
        colors: {
          light: { surface: '#1D1B1C', surfaceHeader: '#123535' },
        },
      },
    });
    assert.ok(result.theme, 'Updated response should include theme');
    assert.strictEqual(result.theme.colors?.light?.surface, '#1D1B1C');
  });

  after(async () => {
    if (feedId) {
      try {
        await client.customFeeds.delete(feedId);
        console.log(`  [cleanup] Deleted themed feed ${feedId}`);
      } catch {
        console.log(`  [cleanup] Could not delete themed feed ${feedId}`);
      }
    }
  });
});

// ---------------------------------------------------------------------------
// 4. Write Ops (Mastodon)
// ---------------------------------------------------------------------------

describe('Write Ops - Mastodon', { concurrency: false }, () => {
  let postId: string | null = null;
  let skipped = false;

  it('should create a post (mastodon)', async () => {
    try {
      const result: any = await client.feeds.createPost(
        {
          status: `SDK integration test (mastodon) -- ${Date.now()}. Safe to delete.`,
          visibility: 'public',
        },
        'mastodon',
      );
      postId = result?.id;
      assert.ok(postId, 'Should return a post ID');
    } catch (err) {
      // 404 here means the test account has no Mastodon linked account — the
      // case this test already intends to skip (Surf returns not-found, not 401/403).
      if (isScopeOrAuth(err) || err instanceof SurfNotFoundError) {
        skipped = true;
        console.log('  [skip] No mastodon linked account or missing write scope');
        return;
      }
      throw err;
    }
  });

  it('should favourite the post', async () => {
    if (skipped || !postId) return;
    const result = await client.feeds.favourite(postId, 'mastodon');
    assert.ok(result !== undefined);
  });

  it('should unfavourite the post', async () => {
    if (skipped || !postId) return;
    const result = await client.feeds.unfavourite(postId, 'mastodon');
    assert.ok(result !== undefined);
  });

  it('should bookmark the post', async () => {
    if (skipped || !postId) return;
    // Bookmark has no AT Protocol equivalent (the Bluesky bridge doesn't
    // implement it), so a Bluesky-backed account returns 404. Tolerate that;
    // bookmark works for native Mastodon/ActivityPub accounts.
    try {
      const result = await client.feeds.bookmark(postId, 'mastodon');
      assert.ok(result !== undefined);
    } catch (err: any) {
      const status = err?.statusCode ?? err?.status;
      if (status === 404 || err?.errorCode === 'not_found' ||
          String(err?.message ?? '').toLowerCase().includes('not found')) {
        console.log('  [skip] Bookmark not supported for Bluesky-backed posts');
        return;
      }
      throw err;
    }
  });

  it('should unbookmark the post', async () => {
    if (skipped || !postId) return;
    // Unbookmark not strictly required, but test it before delete
    try {
      await client.feeds.unbookmark(postId, 'mastodon');
    } catch {
      // Some servers don't support unbookmark via API
    }
  });

  // Cleanup
  after(async () => {
    if (postId) {
      try {
        await client.feeds.deletePost(postId, 'mastodon');
        console.log(`  [cleanup] Deleted mastodon post ${postId}`);
      } catch {
        console.log(`  [cleanup] Could not delete mastodon post ${postId}`);
      }
    }
  });
});

// ---------------------------------------------------------------------------
// 5. Write Ops (Bluesky)
// ---------------------------------------------------------------------------

describe('Write Ops - Bluesky', { concurrency: false }, () => {
  let postId: string | null = null;
  let skipped = false;

  it('should create a post (bluesky)', async () => {
    try {
      const result: any = await client.feeds.createPost(
        {
          status: `SDK integration test (bluesky) -- ${Date.now()}. Safe to delete.`,
          visibility: 'public',
        },
        'bluesky',
      );
      postId = result?.id;
      assert.ok(postId, 'Should return a post ID');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        skipped = true;
        console.log('  [skip] No bluesky linked account or missing write scope');
        return;
      }
      throw err;
    }
  });

  it('should favourite the post', async () => {
    if (skipped || !postId) return;
    const result = await client.feeds.favourite(postId, 'bluesky');
    assert.ok(result !== undefined);
  });

  // Cleanup
  after(async () => {
    if (postId) {
      try {
        await client.feeds.deletePost(postId, 'bluesky');
        console.log(`  [cleanup] Deleted bluesky post ${postId}`);
      } catch {
        console.log(`  [cleanup] Could not delete bluesky post ${postId}`);
      }
    }
  });
});

// ---------------------------------------------------------------------------
// 6. AI
// ---------------------------------------------------------------------------

describe('AI', { concurrency: false }, () => {
  let skipped = false;

  it('should answer an AI query', async () => {
    try {
      const result: any = await client.ai.ask('What is happening in technology today?');
      assert.ok(result, 'Should return an AI response');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        skipped = true;
        console.log('  [skip] Token lacks use:ai scope');
        return;
      }
      throw err;
    }
  });

  it('should generate a feed summary', async () => {
    if (skipped) return;
    try {
      const result: any = await client.ai.feedSummary('surf/topic/technology', 10);
      assert.ok(result, 'Should return a feed summary');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        console.log('  [skip] Token lacks use:ai scope');
        return;
      }
      throw err;
    }
  });
});

// ---------------------------------------------------------------------------
// 6b. Media — AI image generation
// Gated: GPU-bound (20–60s) and burns the 20/day image quota, so it only runs
// when SURF_RUN_AI_IMAGE_TESTS=1. Verifies request shape + response parsing.
// ---------------------------------------------------------------------------

describe('Media (AI image generation)', { concurrency: false }, () => {
  const runImageTests = process.env.SURF_RUN_AI_IMAGE_TESTS === '1';

  // Submit is async and returns immediately, so no long timeout is needed; we
  // disable retries so a 429 daily-cap response (with a long Retry-After) is
  // surfaced for a clean skip instead of stalling the run.
  const imageClient = new SurfClient({
    apiKey: API_TOKEN,
    baseUrl: BASE_URL,
    maxRetries: 0,
  });

  it(
    'should generate a feed cover image',
    {
      skip: runImageTests
        ? false
        : 'set SURF_RUN_AI_IMAGE_TESTS=1 to run (consumes the 20/day GPU image quota)',
    },
    async () => {
      try {
        // Submit only (async): validates the { key, url, status } contract without
        // burning ~90s polling for the image.
        const job = await imageClient.media.generateImage(
          'a calm minimalist landscape, soft pastels',
          { skipRefiner: true },
        );
        assert.ok(job?.key, 'Should return a job key');
        assert.ok(job?.url, 'Should return the eventual image URL');
        assert.equal(job?.status, 'pending', 'Submit status should be pending');
      } catch (err) {
        if (isScopeOrAuth(err)) {
          console.log('  [skip] Token lacks use:ai scope');
          return;
        }
        // Expected operational states: daily cap hit (429) or service down (502/503).
        const status = err instanceof SurfAPIError ? err.statusCode : 0;
        if (status === 429 || status === 502 || status === 503) {
          console.log(`  [skip] image generation unavailable (HTTP ${status})`);
          return;
        }
        throw err;
      }
    },
  );
});

// ---------------------------------------------------------------------------
// 6b. Paginator
// ---------------------------------------------------------------------------

describe('Paginator', { concurrency: false }, () => {
  // paginate() targets object-response endpoints: {"<key>": [...], "cursor": "..."}.
  // /feed/posts may return a bare array on some server configs, in which case
  // paginate() throws SurfAPIError(errorCode="invalid_response"). Both tests
  // catch that error and return early (skip), consistent with Go/Python handling.

  it('should respect limit and not throw', async (t) => {
    const items: any[] = [];
    try {
      for await (const post of client.paginate(
        '/feed/posts', 'posts',
        { surf_id: 'surf/topic/technology', limit: 2 },
        4,
      )) {
        items.push(post);
      }
    } catch (err: any) {
      if (err?.errorCode === 'invalid_response') {
        t.skip('Endpoint returns a bare array; paginate() requires an object response');
        return;
      }
      throw err;
    }
    assert.ok(items.length <= 4, `limit=4 must be respected, got ${items.length}`);
  });

  it('should stop cleanly for a missing key', async (t) => {
    const items: any[] = [];
    try {
      for await (const item of client.paginate(
        '/feed/posts', 'nonexistent_key_xyz',
        { surf_id: 'surf/topic/technology' },
      )) {
        items.push(item);
      }
    } catch (err: any) {
      if (err?.errorCode === 'invalid_response') {
        t.skip('Endpoint returns a bare array; paginate() requires an object response');
        return;
      }
      throw err;
    }
    assert.strictEqual(items.length, 0, 'Missing key should yield nothing');
  });
});

// ---------------------------------------------------------------------------
// 6c. RTB (Real-Time Bidding)
// ---------------------------------------------------------------------------

// RTB lives at surf.social/devportal/v1/rtb, distinct from the main client's
// api.surf.social/v1. Override with SURF_RTB_BASE_URL if needed.
const RTB_BASE_URL = (process.env.SURF_RTB_BASE_URL ?? 'https://surf.social').replace(/\/+$/, '');
const rtb = new SurfRTBClient({ apiKey: API_TOKEN, baseUrl: RTB_BASE_URL });

describe('RTB', { concurrency: false }, () => {
  let skipped = false;

  it('should place a sandbox bid (no real spend)', async () => {
    try {
      // sandbox: true -> server returns synthetic bids, no publisher config needed.
      const result: any = await rtb.bid(
        {
          id: 'sdk-rtb-test-1',
          imp: [{ id: '1', banner: { w: 300, h: 250 } }],
        },
        true,
      );
      assert.ok(result !== undefined, 'Should return a bid response');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        skipped = true;
        console.log('  [skip] Token lacks rtb:bid scope');
        return;
      }
      throw err;
    }
  });

  it('should get RTB reports', async () => {
    if (skipped) return;
    try {
      const result: any = await rtb.reports(7, 'day');
      assert.ok(result !== undefined, 'Should return reports');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        console.log('  [skip] Token lacks rtb:reports scope');
        return;
      }
      throw err;
    }
  });

  it('should get RTB config', async () => {
    if (skipped) return;
    try {
      const result: any = await rtb.config();
      assert.ok(result !== undefined, 'Should return config');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        console.log('  [skip] Token lacks rtb scope for config');
        return;
      }
      // The account may not be a registered RTB publisher; the API correctly
      // returns 503 "could not be initialized" in that case — tolerate it.
      if (String((err as any)?.message ?? '').includes('could not be initialized')) {
        console.log('  [skip] Account has no RTB publisher config');
        return;
      }
      throw err;
    }
  });

  it('should list RTB scopes', async () => {
    if (skipped) return;
    try {
      const result = await rtb.scopes();
      assert.ok(Array.isArray(result), 'scopes() should return an array');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        console.log('  [skip] Token lacks rtb scope for scopes listing');
        return;
      }
      throw err;
    }
  });

  it('should get ads.txt entry', async () => {
    if (skipped) return;
    try {
      const result: any = await rtb.adsTxt();
      assert.ok(result !== undefined, 'Should return ads.txt entry');
    } catch (err) {
      if (isScopeOrAuth(err)) {
        console.log('  [skip] Token lacks rtb scope for ads-txt');
        return;
      }
      throw err;
    }
  });

  it('should throw a typed auth error for an invalid RTB token', async () => {
    const badRtb = new SurfRTBClient({ apiKey: 'invalid_token_xxx', baseUrl: RTB_BASE_URL });
    try {
      await badRtb.bid({ id: 'sdk-rtb-bad', imp: [{ id: '1', banner: { w: 300, h: 250 } }] }, true);
      assert.fail('Should have thrown SurfAuthError or SurfScopeError');
    } catch (err) {
      assert.ok(
        isScopeOrAuth(err),
        `Expected SurfAuthError/SurfScopeError, got ${(err as Error).constructor.name}`,
      );
    }
  });
});

// ---------------------------------------------------------------------------
// 7. Error Handling
// ---------------------------------------------------------------------------

describe('Error Handling', { concurrency: false }, () => {
  it('should return 401 for invalid token', async () => {
    const badClient = new SurfClient({ apiKey: 'invalid_token_xxx', baseUrl: BASE_URL });
    try {
      await badClient.feeds.get('surf/topic/technology');
      assert.fail('Should have thrown SurfAuthError');
    } catch (err) {
      assert.ok(err instanceof SurfAuthError, `Expected SurfAuthError, got ${(err as Error).constructor.name}`);
      assert.equal((err as SurfAuthError).statusCode, 401);
    }
  });

  it('should populate rate limit headers', async () => {
    // Make any request and check that rateLimit is populated
    await client.feeds.get('surf/topic/technology');
    assert.ok(client.rateLimit, 'rateLimit should be populated after a request');
    assert.ok(typeof client.rateLimit.limit === 'number', 'rateLimit.limit should be a number');
    assert.ok(typeof client.rateLimit.remaining === 'number', 'rateLimit.remaining should be a number');
  });
});
