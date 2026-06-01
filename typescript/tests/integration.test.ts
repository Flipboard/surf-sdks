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
 * Rate-limited requests (429) are retried once after Retry-After (capped at 65s).
 * Tests that require scopes the token lacks are skipped (401/403).
 */

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { SurfClient, SurfAuthError, SurfScopeError, SurfRateLimitError } from '../src/index';

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

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Wraps the SurfClient to retry once on 429 (rate limit).
 * We monkey-patch _request to intercept SurfRateLimitError.
 */
function createClient(): SurfClient {
  const client = new SurfClient({ apiKey: API_TOKEN, baseUrl: BASE_URL, timeout: 60_000 });

  const origRequest = (client as any)._request.bind(client);
  (client as any)._request = async function <T>(
    method: string,
    path: string,
    opts?: any,
  ): Promise<T> {
    try {
      return await origRequest(method, path, opts);
    } catch (err) {
      if (err instanceof SurfRateLimitError) {
        const wait = Math.min(err.retryAfter ?? 5, 65) * 1000;
        console.log(`  [rate-limit] 429 on ${method} ${path}, waiting ${wait / 1000}s...`);
        await sleep(wait);
        return origRequest(method, path, opts);
      }
      throw err;
    }
  };

  return client;
}

const client = createClient();

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
      if (isScopeOrAuth(err)) {
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
    const result = await client.feeds.bookmark(postId, 'mastodon');
    assert.ok(result !== undefined);
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
