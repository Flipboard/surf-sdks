# surf-go

Go SDK for the [Surf API](https://developers.surf.social). Coming soon.

```go
import "github.com/Flipboard/surf-sdks/go"

client := surf.NewClient("surf_sk_live_your_token_here")
posts, err := client.Feeds.GetPosts("surf/topic/technology", nil)
```
