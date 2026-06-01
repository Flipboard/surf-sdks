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
