package surf

import "encoding/json"

// Post is a Mastodon-compatible status object returned by the Surf API.
type Post struct {
	ID                 string            `json:"id"`
	Content            string            `json:"content"`
	CreatedAt          string            `json:"created_at"`
	URL                string            `json:"url"`
	FavouritesCount    int               `json:"favourites_count"`
	ReblogsCount       int               `json:"reblogs_count"`
	RepliesCount       int               `json:"replies_count"`
	Visibility         string            `json:"visibility"`
	Sensitive          bool              `json:"sensitive"`
	SpoilerText        string            `json:"spoiler_text,omitempty"`
	Language           *string           `json:"language,omitempty"`
	InReplyToID        *string           `json:"in_reply_to_id,omitempty"`
	InReplyToAccountID *string           `json:"in_reply_to_account_id,omitempty"`
	Account            *PostAccount      `json:"account,omitempty"`
	Card               *Card             `json:"card,omitempty"`
	MediaAttachments   []MediaAttachment `json:"media_attachments,omitempty"`
	Reblog             *Post             `json:"reblog,omitempty"`
	Quote              *Post             `json:"quote,omitempty"`
	PostType           *string           `json:"post_type,omitempty"`
	Topics             []string          `json:"topics,omitempty"`
	Duration           *int              `json:"duration,omitempty"`
	Podcast            *bool             `json:"podcast,omitempty"`
	Paywall            *bool             `json:"paywall,omitempty"`
	Orientation        *string           `json:"orientation,omitempty"`
	Document           *PostDocument     `json:"document,omitempty"`
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

// PodcastEpisodeSearchResult is one transcript chunk matching a semantic
// podcast episode search.
type PodcastEpisodeSearchResult struct {
	EpisodeURL string `json:"episode_url"`
	// EpisodeURLHash is the SHA1 hex of the full audio URL — the episode's
	// stable ID across the audio APIs (see the EpisodeURLHash function).
	EpisodeURLHash string `json:"episode_url_hash"`
	// FlyfID is the podcast feed ID (SHA1 hex of the full RSS feed URL).
	FlyfID       *string `json:"flyf_id,omitempty"`
	PodcastName  *string `json:"podcast_name,omitempty"`
	EpisodeTitle *string `json:"episode_title,omitempty"`
	// Score is the semantic similarity (0-1, higher is better).
	Score             float64  `json:"score"`
	ChunkStartSeconds *float64 `json:"chunk_start_seconds,omitempty"`
	ChunkEndSeconds   *float64 `json:"chunk_end_seconds,omitempty"`
	Preview           *string  `json:"preview,omitempty"`
}

// PodcastEpisodeSearchResponse is the response of Audio.SearchPodcastEpisodes.
type PodcastEpisodeSearchResponse struct {
	OK      bool                         `json:"ok"`
	Query   string                       `json:"query"`
	FlyfID  *string                      `json:"flyf_id,omitempty"`
	Results []PodcastEpisodeSearchResult `json:"results"`
	Total   int                          `json:"total"`
}

// PodcastGuestAppearance is one detected episode appearance of a podcast
// guest or host.
type PodcastGuestAppearance struct {
	FlyfID         *string `json:"flyf_id,omitempty"`
	PodcastName    *string `json:"podcast_name,omitempty"`
	EpisodeURL     string  `json:"episode_url"`
	EpisodeURLHash string  `json:"episode_url_hash"`
	// Role is the detected role in the episode (e.g. "host", "guest").
	Role *string `json:"role,omitempty"`
	// Confidence is the detection confidence (0-1).
	Confidence          *float64 `json:"confidence,omitempty"`
	SpeakingTimeSeconds *float64 `json:"speaking_time_seconds,omitempty"`
	DetectedAt          *string  `json:"detected_at,omitempty"`
}

// PodcastGuest is a podcast guest or host detected via transcript and
// speaker analysis.
type PodcastGuest struct {
	Name string `json:"name"`
	// Title is the professional title, when known (e.g. "CEO").
	Title          *string `json:"title,omitempty"`
	Organization   *string `json:"organization,omitempty"`
	BlueskyHandle  *string `json:"bluesky_handle,omitempty"`
	MastodonHandle *string `json:"mastodon_handle,omitempty"`
	// Appearances lists episodes this person appeared in, newest first.
	Appearances []PodcastGuestAppearance `json:"appearances,omitempty"`
}

// PodcastGuestSearchResponse is the response of Audio.SearchPodcastGuests.
type PodcastGuestSearchResponse struct {
	OK     bool           `json:"ok"`
	Query  string         `json:"query"`
	Guests []PodcastGuest `json:"guests"`
	Total  int            `json:"total"`
}

// PodcastMentionTimestamp is one mention time range within an episode,
// in seconds.
type PodcastMentionTimestamp struct {
	Start float64 `json:"start"`
	End   float64 `json:"end"`
}

// PodcastMention is all mentions of one entity within one episode.
type PodcastMention struct {
	EpisodeURL     string  `json:"episode_url"`
	EpisodeURLHash string  `json:"episode_url_hash"`
	FlyfID         *string `json:"flyf_id,omitempty"`
	// Entity is the name as spoken/recognized (original casing).
	Entity string `json:"entity"`
	// EntityType is "person", "organization", or "location".
	EntityType        string   `json:"entity_type"`
	MentionCount      int      `json:"mention_count"`
	FirstStartSeconds *float64 `json:"first_start_seconds,omitempty"`
	// Timestamps holds up to 50 mention time ranges per episode.
	Timestamps []PodcastMentionTimestamp `json:"timestamps,omitempty"`
	// CreatedAt is when the episode was indexed.
	CreatedAt *string `json:"created_at,omitempty"`
}

// PodcastMentionsResponse is the response of Audio.GetPodcastMentions.
type PodcastMentionsResponse struct {
	OK bool `json:"ok"`
	// Entity is the normalized (lowercased) entity name that was matched.
	Entity     string           `json:"entity"`
	EntityType *string          `json:"entity_type,omitempty"`
	FlyfID     *string          `json:"flyf_id,omitempty"`
	Mentions   []PodcastMention `json:"mentions"`
	// Total is the number of rows returned (page size, not the global count).
	Total  int `json:"total"`
	Limit  int `json:"limit"`
	Offset int `json:"offset"`
}

// PodcastSponsorAd is one classified podcast ad placement in one episode.
type PodcastSponsorAd struct {
	EpisodeURL     string  `json:"episode_url"`
	EpisodeURLHash string  `json:"episode_url_hash"`
	FlyfID         *string `json:"flyf_id,omitempty"`
	// Company is the advertiser company name.
	Company string  `json:"company"`
	Product *string `json:"product,omitempty"`
	// Category is the advertiser category (e.g. "technology", "finance").
	Category *string `json:"category,omitempty"`
	// AdFormat is the ad format (e.g. "host_read", "produced").
	AdFormat        *string  `json:"ad_format,omitempty"`
	PromoCode       *string  `json:"promo_code,omitempty"`
	StartSeconds    *float64 `json:"start_seconds,omitempty"`
	EndSeconds      *float64 `json:"end_seconds,omitempty"`
	DurationSeconds *float64 `json:"duration_seconds,omitempty"`
	// Confidence is the ad detection confidence (0-1).
	Confidence *float64 `json:"confidence,omitempty"`
	// AdTextPreview is a preview of the transcribed ad read (up to 1024 chars).
	AdTextPreview *string `json:"ad_text_preview,omitempty"`
	ModelVersion  *string `json:"model_version,omitempty"`
	// CreatedAt is when the ad was detected and classified.
	CreatedAt *string `json:"created_at,omitempty"`
}

// PodcastSponsorsResponse is the response of Audio.GetPodcastSponsors.
type PodcastSponsorsResponse struct {
	OK bool `json:"ok"`
	// Company is the normalized (lowercased) company name that was matched.
	Company        *string            `json:"company,omitempty"`
	EpisodeURLHash *string            `json:"episode_url_hash,omitempty"`
	FlyfID         *string            `json:"flyf_id,omitempty"`
	Sponsors       []PodcastSponsorAd `json:"sponsors"`
	// Total is the number of rows returned (page size, not the global count).
	Total  int `json:"total"`
	Limit  int `json:"limit"`
	Offset int `json:"offset"`
}

// PodcastFactCheck is one fact-checked claim from a podcast episode.
type PodcastFactCheck struct {
	// ClaimIndex is the position of the claim within the episode's fact
	// checks (0-based).
	ClaimIndex int    `json:"claim_index"`
	ClaimText  string `json:"claim_text"`
	// ClaimType is the kind of claim (e.g. "statistic", "event", "quote").
	ClaimType *string `json:"claim_type,omitempty"`
	// TimestampSeconds is where the claim is made in the episode.
	TimestampSeconds *float64 `json:"timestamp_seconds,omitempty"`
	// Verdict is the fact-check verdict (e.g. "verified", "disputed",
	// "false", "unverifiable").
	Verdict string `json:"verdict"`
	// Confidence is the verdict confidence (0-1).
	Confidence  *float64 `json:"confidence,omitempty"`
	Explanation *string  `json:"explanation,omitempty"`
	// Sources holds the citation objects backing the verdict.
	Sources []map[string]any `json:"sources,omitempty"`
	// SearchQueries lists the web searches run while checking the claim.
	SearchQueries []string `json:"search_queries,omitempty"`
}

// PodcastFactChecksResponse is the response of Audio.GetFactChecks.
type PodcastFactChecksResponse struct {
	OK         bool               `json:"ok"`
	EpisodeURL string             `json:"episode_url"`
	FactChecks []PodcastFactCheck `json:"fact_checks"`
	Total      int                `json:"total"`
	// Summary counts claims per verdict (e.g. verified, disputed).
	Summary map[string]int `json:"summary,omitempty"`
	Error   *string        `json:"error,omitempty"`
}

// PodcastTranslation is a stored transcript translation for one episode and
// language.
type PodcastTranslation struct {
	// SourceLanguage is the detected language of the original transcript.
	SourceLanguage *string `json:"source_language,omitempty"`
	TargetLanguage *string `json:"target_language,omitempty"`
	// TranslatedTranscript is the full translated transcript text.
	TranslatedTranscript string `json:"translated_transcript"`
	// TranslatedSegments holds the timestamped translated segments.
	TranslatedSegments []map[string]any `json:"translated_segments,omitempty"`
	// AudioURL is the translated TTS audio URL, when audio was generated.
	AudioURL             *string  `json:"audio_url,omitempty"`
	AudioDurationSeconds *float64 `json:"audio_duration_seconds,omitempty"`
	// TTSVoice is the voice used for the translated audio.
	TTSVoice                *string  `json:"tts_voice,omitempty"`
	WordCount               *int     `json:"word_count,omitempty"`
	OriginalDurationSeconds *float64 `json:"original_duration_seconds,omitempty"`
}

// PodcastTranslationResponse is the response of Audio.GetTranslation.
type PodcastTranslationResponse struct {
	OK         bool   `json:"ok"`
	EpisodeURL string `json:"episode_url"`
	Language   string `json:"language"`
	// Translation is nil when no stored translation exists (the endpoint
	// then returns a 404 API error).
	Translation *PodcastTranslation `json:"translation,omitempty"`
	Error       *string             `json:"error,omitempty"`
}

// PodcastCatchUpResponse is the response of Audio.GetCatchUp.
type PodcastCatchUpResponse struct {
	OK         bool   `json:"ok"`
	EpisodeURL string `json:"episode_url"`
	// TimestampSeconds echoes the requested playback position.
	TimestampSeconds float64 `json:"timestamp_seconds"`
	// Summary is a prose summary of everything before the timestamp.
	Summary       *string  `json:"summary,omitempty"`
	TopicsCovered []string `json:"topics_covered"`
	KeyPoints     []string `json:"key_points"`
	// MissedDurationSeconds is how much episode time the summary covers.
	MissedDurationSeconds *float64 `json:"missed_duration_seconds,omitempty"`
	Error                 *string  `json:"error,omitempty"`
}

// PodcastTopicMatch is one transcript passage matching a skip-to-topic query.
type PodcastTopicMatch struct {
	StartSeconds *float64 `json:"start_seconds,omitempty"`
	EndSeconds   *float64 `json:"end_seconds,omitempty"`
	// TextPreview previews the matching transcript passage.
	TextPreview *string `json:"text_preview,omitempty"`
	// Score is the relevance score (higher is more relevant).
	Score *float64 `json:"score,omitempty"`
}

// PodcastTopicSeekResponse is the response of Audio.SkipToTopic.
type PodcastTopicSeekResponse struct {
	OK         bool   `json:"ok"`
	EpisodeURL string `json:"episode_url"`
	Topic      string `json:"topic"`
	// Matches come back best first; empty with OK=true means nothing scored
	// above the relevance floor.
	Matches []PodcastTopicMatch `json:"matches"`
	Total   int                 `json:"total"`
	Error   *string             `json:"error,omitempty"`
}

// PopularShow is one ranked show row from a popular-shows snapshot.
type PopularShow struct {
	// Rank is the position in the chart (1-based).
	Rank int `json:"rank"`
	// Score is the blended popularity score (higher is more popular).
	Score float64 `json:"score"`
	// FlyfID is the podcast feed ID (SHA1 hex of the full RSS feed URL).
	FlyfID *string `json:"flyf_id,omitempty"`
	// Ingested reports whether the show is already ingested and playable on Surf.
	Ingested   bool    `json:"ingested"`
	FeedURL    *string `json:"feed_url,omitempty"`
	Title      *string `json:"title,omitempty"`
	ArtworkURL *string `json:"artwork_url,omitempty"`
	ITunesID   *int64  `json:"itunes_id,omitempty"`
	// PodcastIndexID is the Podcast Index feed id.
	PodcastIndexID *int64 `json:"podcastindex_id,omitempty"`
	// AppleRank is the rank on the Apple top chart, when charted there.
	AppleRank *int `json:"apple_rank,omitempty"`
	// PITrendRank is the rank on Podcast Index trending, when charted there.
	PITrendRank *int `json:"pi_trend_rank,omitempty"`
	// Engagement7d is the fediverse engagement over the last 7 days.
	Engagement7d *int64 `json:"engagement_7d,omitempty"`
	// CreatedAt is when the snapshot row was written.
	CreatedAt *string `json:"created_at,omitempty"`
}

// PopularShowsResponse is the response of Audio.GetPopularShows.
type PopularShowsResponse struct {
	OK bool `json:"ok"`
	// Region echoes the (normalized) chart region.
	Region string `json:"region"`
	// Category echoes the (normalized) chart category.
	Category string `json:"category"`
	// SnapshotDate is the ISO date of the snapshot served; nil when no
	// snapshot exists yet.
	SnapshotDate *string `json:"snapshot_date,omitempty"`
	IngestedOnly bool    `json:"ingested_only"`
	Limit        int     `json:"limit"`
	// Shows come back in rank order.
	Shows []PopularShow `json:"shows"`
	// Total is the number of rows returned.
	Total int     `json:"total"`
	Error *string `json:"error,omitempty"`
}

// PopularEpisode is one ranked episode row from a hot-episodes snapshot.
type PopularEpisode struct {
	// Rank is the position in the chart (1-based).
	Rank int `json:"rank"`
	// Score is the engagement-based popularity score (higher is hotter).
	Score float64 `json:"score"`
	// EpisodeURLHash is the SHA1 hex of the full audio URL — the episode's
	// stable ID across the audio APIs (see the EpisodeURLHash function).
	EpisodeURLHash string `json:"episode_url_hash"`
	// EpisodeURL is the episode's audio file URL.
	EpisodeURL string `json:"episode_url"`
	// FlyfID is the podcast feed ID (SHA1 hex of the full RSS feed URL).
	FlyfID     *string `json:"flyf_id,omitempty"`
	Title      *string `json:"title,omitempty"`
	ShowTitle  *string `json:"show_title,omitempty"`
	ArtworkURL *string `json:"artwork_url,omitempty"`
	// EngagementSum is favourites + reblogs + replies across fediverse posts
	// about the episode.
	EngagementSum int64 `json:"engagement_sum"`
	// PostCount is the number of fediverse posts referencing the episode.
	PostCount int `json:"post_count"`
	// CreatedAt is when the snapshot row was written.
	CreatedAt *string `json:"created_at,omitempty"`
}

// PopularEpisodesResponse is the response of Audio.GetPopularEpisodes.
type PopularEpisodesResponse struct {
	OK bool `json:"ok"`
	// SnapshotDate is the ISO date of the snapshot served; nil when no
	// snapshot exists yet.
	SnapshotDate *string `json:"snapshot_date,omitempty"`
	Limit        int     `json:"limit"`
	// Episodes come back in rank order.
	Episodes []PopularEpisode `json:"episodes"`
	// Total is the number of rows returned.
	Total int     `json:"total"`
	Error *string `json:"error,omitempty"`
}
