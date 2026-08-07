package surf

import "encoding/json"

// Post is a Mastodon-compatible status object returned by the Surf API.
type Post struct {
	ID               string            `json:"id"`
	Content          string            `json:"content"`
	CreatedAt        string            `json:"created_at"`
	URL              string            `json:"url"`
	FavouritesCount  int               `json:"favourites_count"`
	ReblogsCount     int               `json:"reblogs_count"`
	RepliesCount     int               `json:"replies_count"`
	Visibility       string            `json:"visibility"`
	Sensitive        bool              `json:"sensitive"`
	SpoilerText      string            `json:"spoiler_text,omitempty"`
	Language         *string           `json:"language,omitempty"`
	InReplyToID      *string           `json:"in_reply_to_id,omitempty"`
	InReplyToAccountID *string         `json:"in_reply_to_account_id,omitempty"`
	Account          *PostAccount      `json:"account,omitempty"`
	Card             *Card             `json:"card,omitempty"`
	MediaAttachments []MediaAttachment `json:"media_attachments,omitempty"`
	Reblog           *Post             `json:"reblog,omitempty"`
	Quote            *Post             `json:"quote,omitempty"`
	PostType         *string           `json:"post_type,omitempty"`
	Topics           []string          `json:"topics,omitempty"`
	Duration         *int              `json:"duration,omitempty"`
	Podcast          *bool             `json:"podcast,omitempty"`
	Paywall          *bool             `json:"paywall,omitempty"`
	Orientation      *string           `json:"orientation,omitempty"`
	Document         *PostDocument     `json:"document,omitempty"`
}

// PostDocument is the optional longform-document summary attached to a Post
// that links to a standard.site / Leaflet document.
type PostDocument struct {
	Title          string   `json:"title,omitempty"`
	Description    string   `json:"description,omitempty"`
	CoverImageURL  string   `json:"cover_image_url,omitempty"`
	Tags           []string `json:"tags,omitempty"`
	PublicationURI string   `json:"publication_uri,omitempty"`
}

// PostAccount is the author of a post.
type PostAccount struct {
	ID             string `json:"id"`
	Username       string `json:"username"`
	DisplayName    string `json:"display_name"`
	URL            string `json:"url"`
	Avatar         string `json:"avatar"`
	FollowersCount int    `json:"followers_count"`
	FollowingCount int    `json:"following_count"`
	StatusesCount  int    `json:"statuses_count"`
	Bot            bool   `json:"bot"`
}

// Card is a link preview on a post.
type Card struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	URL         string `json:"url"`
	Image       *Image `json:"image,omitempty"`
	Type        string `json:"type,omitempty"`
}

// MediaAttachment is a media file on a post.
type MediaAttachment struct {
	ID          string `json:"id"`
	Type        string `json:"type"`
	URL         string `json:"url"`
	PreviewURL  string `json:"preview_url,omitempty"`
	Description string `json:"description,omitempty"`
}

// FeedMetaTyped is typed feed metadata (vs raw json.RawMessage from FeedsAPI.Get).
type FeedMetaTyped struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Type        string `json:"type"`
	SurfID      string `json:"surf_id"`
	Author      string `json:"author"`
	Image       *Image `json:"image,omitempty"`
	Subscribers int    `json:"subscribers"`
}

// Image is an image with size variants.
type Image struct {
	Original *ImageSize `json:"original,omitempty"`
	XLarge   *ImageSize `json:"xlarge,omitempty"`
	Large    *ImageSize `json:"large,omitempty"`
	Medium   *ImageSize `json:"medium,omitempty"`
	Small    *ImageSize `json:"small,omitempty"`
}

// ImageSize is a single image size variant.
type ImageSize struct {
	URL    string `json:"url"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
}

// Topic is a topic assignment.
type Topic struct {
	Name      string `json:"name"`
	Score     int    `json:"score"`
	TopicType string `json:"topic_type"`
}

// TopicsResult is the response from GET /content/topics.
type TopicsResult struct {
	URL       string   `json:"url"`
	Topics    []Topic  `json:"topics"`
	Tags      []string `json:"tags"`
	PostTypes []string `json:"post_types"`
	Language  *string  `json:"language,omitempty"`
}

// ResolveResult is the response from GET /content/resolve.
type ResolveResult struct {
	InputURL string   `json:"input_url"`
	FinalURL string   `json:"final_url"`
	Status   int      `json:"status"`
	Chain    []string `json:"chain"`
}

// EnrichmentDataTyped is the response from GET /content/enrich.
type EnrichmentDataTyped struct {
	PostID          string   `json:"post_id"`
	Topics          []Topic  `json:"topics"`
	PostTypes       []string `json:"post_types"`
	Language        *string  `json:"language,omitempty"`
	NSFW            bool     `json:"nsfw"`
	ClaimScore      float64  `json:"claim_score"`
	Tags            []string `json:"tags"`
	ContainsURL     bool     `json:"contains_url"`
	FlusURL         *string  `json:"flus_url,omitempty"`
	FlusDomain      *string  `json:"flus_domain,omitempty"`
	DomainBoost     float64  `json:"domain_boost"`
	Duration        *int     `json:"duration,omitempty"`
	Podcast         bool     `json:"podcast"`
	Orientation     *string  `json:"orientation,omitempty"`
	Paywall         bool     `json:"paywall"`
	FavouritesCount int      `json:"favourites_count"`
	ReblogsCount    int      `json:"reblogs_count"`
	RepliesCount    int      `json:"replies_count"`
}

// ModerationResultTyped is the response from GET /image/moderate.
type ModerationResultTyped struct {
	NSFW             bool              `json:"nsfw"`
	Moderated        bool              `json:"moderated"`
	ModerationLabels []ModerationLabel `json:"moderationLabels"`
}

// ModerationLabel is a single moderation label.
type ModerationLabel struct {
	Name       string  `json:"name"`
	Confidence float64 `json:"confidence"`
	ParentName string  `json:"parentName,omitempty"`
}

// ConnectedApp is an OAuth-authorized third-party app.
type ConnectedApp struct {
	AuthorizationID int    `json:"authorization_id"`
	AppID           string `json:"app_id"`
	AppName         string `json:"app_name"`
	LogoURL         string `json:"logo_url,omitempty"`
	Scopes          string `json:"scopes"`
	AuthorizedAt    string `json:"authorized_at"`
	LastUsed        string `json:"last_used"`
}

// Document is a longform document (standard.site / Leaflet) returned by
// LongformAPI.Document. ContentHTML is populated for the "html" format (the
// default); Pages carries the raw block pages for the "blocks" format.
type Document struct {
	ID             string            `json:"id"`
	Title          string            `json:"title,omitempty"`
	Description    string            `json:"description,omitempty"`
	PublishedAt    string            `json:"published_at,omitempty"`
	Path           string            `json:"path,omitempty"`
	CoverImageURL  string            `json:"cover_image_url,omitempty"`
	Tags           []string          `json:"tags,omitempty"`
	PublicationURI string            `json:"publication_uri,omitempty"`
	Publication    *Publication      `json:"publication,omitempty"`
	Author         *DocumentAuthor   `json:"author,omitempty"`
	CommentsCount  int               `json:"comments_count"`
	ContentHTML    string            `json:"content_html,omitempty"`
	Pages          []json.RawMessage `json:"pages,omitempty"`
}

// DocumentAuthor identifies the author of a longform document.
type DocumentAuthor struct {
	DID    string `json:"did"`
	Handle string `json:"handle,omitempty"`
}

// Publication is a longform publication (standard.site / Leaflet) returned
// by LongformAPI.Publication and LongformAPI.SearchPublications.
type Publication struct {
	URI                  string `json:"uri"`
	Name                 string `json:"name,omitempty"`
	Description          string `json:"description,omitempty"`
	IconURL              string `json:"icon_url,omitempty"`
	DID                  string `json:"did,omitempty"`
	PublisherHandle      string `json:"publisher_handle,omitempty"`
	PublisherDisplayName string `json:"publisher_display_name,omitempty"`
	PublisherAvatar      string `json:"publisher_avatar,omitempty"`
}

// PublicationDocument is a document summary returned by
// LongformAPI.PublicationDocuments.
type PublicationDocument struct {
	URI           string   `json:"uri"`
	Title         string   `json:"title,omitempty"`
	Description   string   `json:"description,omitempty"`
	Path          string   `json:"path,omitempty"`
	CoverImageURL string   `json:"cover_image_url,omitempty"`
	PublishedAt   string   `json:"published_at,omitempty"`
	Tags          []string `json:"tags,omitempty"`
}

// ProfileLink is a link on the user's profile.
type ProfileLink struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	URL   string `json:"url"`
	Icon  string `json:"icon,omitempty"`
	Order int    `json:"order"`
}
