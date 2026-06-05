/**
 * SurfAgent -- AI agent with Surf tools pre-loaded via MCP.
 *
 * Wraps the Claude Agent SDK with the Surf MCP server connected, giving
 * developers a batteries-included agent that can search feeds, discover
 * content, create custom feeds, and interact with the social web using
 * natural language.
 *
 * Requires the `@anthropic-ai/claude-agent-sdk` package:
 *
 *   npm install @anthropic-ai/claude-agent-sdk
 *
 * @example
 * ```ts
 * import { SurfAgent } from '@surf/api';
 *
 * const agent = new SurfAgent({ surfApiKey: 'surf_sk_live_...' });
 * const result = await agent.run(
 *   'Find the top AI feeds on Surf and summarize the latest posts'
 * );
 * console.log(result.text);
 * ```
 */

const MCP_SERVER_URL = 'https://mcp.surf.social/mcp';

const SYSTEM_PROMPT = `You are a helpful assistant with access to the Surf social platform via MCP tools.
Surf aggregates content from Mastodon, Bluesky, and RSS into unified feeds.

Search & Discovery:
- search_surf_feeds: Search for feeds by topic or keyword
- search_posts: Search individual posts across all platforms
- search_accounts: Search accounts across Mastodon and Bluesky
- search_bluesky_users: Search Bluesky users specifically
- search_podcasts: Search podcast feeds
- get_feed_posts: Get posts from any feed
- get_feed_details: Get metadata about a feed
- get_trending_feeds: Discover trending feeds
- get_account: Look up a user profile by handle

AI & Analysis:
- summarize_feed: Get an AI summary of a feed
- ask_about_content: Ask questions about content
- ask_surf: Semantic search via NLWeb

Content & Media:
- resolve_url: Resolve shortened URLs to their destination
- extract_article: Extract article text from a URL
- get_image_info: Get image dimensions and size variants
- text_to_speech: Convert text to speech audio

Create & Manage (authenticated):
- build_custom_feed: Compose a custom feed from sources
- save_custom_feed: Save a custom feed to the user's account
- create_post: Publish a post -- ALWAYS confirm with the user first
- favourite_post: Favourite/like a post
- set_feed_theme: Set visual theme on a custom feed

When searching, use specific terms. When creating feeds, suggest diverse sources.
When summarizing content, be concise and highlight key themes.
Never post without explicit user approval.`;

export interface SurfAgentOptions {
  /** Surf API token (surf_sk_live_...) */
  surfApiKey: string;
  /** Claude model to use. Defaults to claude-sonnet-4-6. */
  model?: string;
  /** Custom system prompt. Defaults to Surf-aware prompt. */
  systemPrompt?: string;
  /** Surf MCP server URL. Defaults to production. */
  mcpServerUrl?: string;
  /** Default max agent turns per run. */
  maxTurns?: number;
  /** Default max spend per run in USD. */
  maxBudgetUsd?: number;
}

export interface SurfAgentResult {
  /** The agent's text response. */
  text: string;
  /** Full message history from the agent run. */
  messages: unknown[];
  /** Number of assistant turns. */
  turns: number;
  /** Why the agent stopped. */
  stopReason: string | undefined;
}

export class SurfAgent {
  private surfApiKey: string;
  private model: string;
  private systemPrompt: string;
  private mcpServerUrl: string;
  private maxTurns: number | undefined;
  private maxBudgetUsd: number | undefined;

  constructor(options: SurfAgentOptions) {
    this.surfApiKey = options.surfApiKey;
    this.model = options.model ?? 'claude-sonnet-4-6';
    this.systemPrompt = options.systemPrompt ?? SYSTEM_PROMPT;
    this.mcpServerUrl = options.mcpServerUrl ?? MCP_SERVER_URL;
    this.maxTurns = options.maxTurns;
    this.maxBudgetUsd = options.maxBudgetUsd;
  }

  private getQueryOptions(overrides?: { maxTurns?: number; maxBudgetUsd?: number }) {
    return {
      model: this.model,
      systemPrompt: this.systemPrompt,
      maxTurns: overrides?.maxTurns ?? this.maxTurns,
      maxBudgetUsd: overrides?.maxBudgetUsd ?? this.maxBudgetUsd,
      mcpServers: {
        surf: {
          type: 'http' as const,
          url: this.mcpServerUrl,
          headers: {
            'X-API-Key': this.surfApiKey,
          },
        },
      },
      permissionMode: 'auto' as const,
      allowedTools: ['mcp__surf__*'],
    };
  }

  /**
   * Run a one-shot agent query.
   *
   * The agent connects to Surf via MCP and can use any of the 8 Surf
   * tools to fulfill the request. All Claude compute runs on your
   * Agent SDK credit.
   */
  async run(
    prompt: string,
    options?: { maxTurns?: number; maxBudgetUsd?: number },
  ): Promise<SurfAgentResult> {
    let query: any;
    try {
      // @ts-ignore -- optional peer dependency, checked at runtime
      const sdk = await import('@anthropic-ai/claude-agent-sdk');
      query = sdk.query;
    } catch {
      throw new Error(
        'SurfAgent requires @anthropic-ai/claude-agent-sdk. ' +
        'Install it with: npm install @anthropic-ai/claude-agent-sdk',
      );
    }

    const queryOptions = this.getQueryOptions(options);
    const messages: unknown[] = [];
    const textParts: string[] = [];
    let turns = 0;
    let stopReason: string | undefined;

    for await (const message of query({ prompt, options: queryOptions })) {
      messages.push(message);
      const msg = message as any;

      if (msg.type === 'assistant') {
        const content = msg.content;
        if (Array.isArray(content)) {
          for (const block of content) {
            if (block.type === 'text') {
              textParts.push(block.text);
            }
          }
        } else if (typeof content === 'string') {
          textParts.push(content);
        }
        turns++;
      }

      if (msg.type === 'result') {
        stopReason = msg.stop_reason;
      }
    }

    return {
      text: textParts.join('\n'),
      messages,
      turns,
      stopReason,
    };
  }

  /**
   * Stream agent messages as they arrive.
   *
   * Yields raw Message objects from the Agent SDK. Useful for
   * building interactive UIs or processing tool calls as they happen.
   */
  async *stream(
    prompt: string,
    options?: { maxTurns?: number; maxBudgetUsd?: number },
  ): AsyncGenerator<unknown> {
    let query: any;
    try {
      // @ts-ignore -- optional peer dependency, checked at runtime
      const sdk = await import('@anthropic-ai/claude-agent-sdk');
      query = sdk.query;
    } catch {
      throw new Error(
        'SurfAgent requires @anthropic-ai/claude-agent-sdk. ' +
        'Install it with: npm install @anthropic-ai/claude-agent-sdk',
      );
    }

    const queryOptions = this.getQueryOptions(options);

    for await (const message of query({ prompt, options: queryOptions })) {
      yield message;
    }
  }
}
