# @surf/api

TypeScript/JavaScript SDK for the [Surf API](https://developers.surf.social).

```bash
npm install @surf/api
```

```typescript
import { SurfClient } from '@surf/api';

const client = new SurfClient({ apiKey: 'surf_sk_live_your_token_here' });
const posts = await client.feeds.getPosts('surf/topic/technology');
```

## AI Agent

Build autonomous agents that interact with the social web. Requires `@anthropic-ai/claude-agent-sdk`:

```bash
npm install @anthropic-ai/claude-agent-sdk
```

```typescript
import { SurfAgent } from '@surf/api';

const agent = new SurfAgent({ surfApiKey: 'surf_sk_live_your_token' });

const result = await agent.run(
  'Find the top AI feeds on Surf and summarize the latest posts'
);
console.log(result.text);
```

By default only read-only tools are enabled. To allow posting, favouriting, and feed creation:

```typescript
const agent = new SurfAgent({ surfApiKey: '...', allowWrites: true });
```

All Claude compute runs on your [Agent SDK credit](https://developers.surf.social/devportal/v1/getting-started#mcp-integration-claude--ai-agents).
