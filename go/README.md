# surf-go

Official Go SDK for the [Surf API](https://developers.surf.social) — v1.0.0 GA.

```go
import "github.com/Flipboard/surf-sdks/go"

client := surf.NewClient("surf_sk_live_your_token_here")
posts, err := client.Feeds.GetPosts("surf/topic/technology", nil)
```
