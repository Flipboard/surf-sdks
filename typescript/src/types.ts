/** Rate limit information from response headers. */
export interface RateLimitInfo {
  limit: number;
  remaining: number;
  reset: string | null;
}

/** Options for creating a SurfClient. */
export interface SurfClientOptions {
  /** API token (surf_sk_live_... or surf_sk_test_...) */
  apiKey: string;
  /** Base URL (default: https://api.surf.social) */
  baseUrl?: string;
  /** Developer-portal base URL for diagnostics/debug bundles (default: https://surf.social/devportal/v1) */
  devportalUrl?: string;
  /** Request timeout in ms (default: 30000) */
  timeout?: number;
  /** Custom fetch implementation (default: global fetch) */
  fetch?: typeof fetch;
  /** Number of retries after the initial attempt on 429, 5xx, or transient network errors (default: 3, i.e. up to 4 total attempts). Set to 0 to disable. */
  maxRetries?: number;
}

/** API error response body. */
export interface SurfErrorBody {
  error: string;
  error_description: string;
}

/** Feed metadata. */
export interface FeedMeta {
  title?: string;
  description?: string;
  type?: string;
  surf_id?: string;
  author?: string;
  image?: Image;
  subscribers?: number;
  [key: string]: unknown;
}

/** Image with size variants. */
export interface Image {
  original?: ImageSize;
  xlarge?: ImageSize;
  large?: ImageSize;
  medium?: ImageSize;
  small?: ImageSize;
}

/** Single image size. */
export interface ImageSize {
  url: string;
  width: number;
  height: number;
}

/** Profile link on a user's profile. */
export interface ProfileLink {
  id?: string;
  title: string;
  url: string;
  icon?: string;
  order?: number;
}

/** Moderation result from NSFW detection. */
export interface ModerationResult {
  nsfw: boolean;
  moderated: boolean;
  moderationLabels?: Array<{
    name: string;
    confidence: number;
    parentName?: string;
  }>;
}

/** Topic assignment on a post or URL. */
export interface Topic {
  name: string;
  score?: number;
  topic_type?: string;
}

/** Author/account on a post. */
export interface PostAccount {
  id: string;
  username: string;
  display_name: string;
  url: string;
  avatar: string;
  followers_count?: number;
  following_count?: number;
  statuses_count?: number;
  bot?: boolean;
}

/** Link preview card on a post. */
export interface Card {
  title: string;
  description: string;
  url: string;
  image?: Image;
  type?: string;
}

/** Media attachment on a post. */
export interface MediaAttachment {
  id: string;
  type: string;
  url: string;
  preview_url?: string;
  description?: string;
}

/** A post/status from the Surf API. */
export interface Post {
  id: string;
  content: string;
  created_at: string;
  url: string;
  favourites_count: number;
  reblogs_count: number;
  replies_count: number;
  visibility: string;
  sensitive: boolean;
  spoiler_text?: string;
  language?: string;
  /** Id of the post this is a reply to; absent when not a reply. */
  in_reply_to_id?: string;
  /** Account id (DID for Bluesky) of the author being replied to; compare to account.id to tell a self-thread from a reply into someone else's thread. Absent when not a reply. */
  in_reply_to_account_id?: string;
  account?: PostAccount;
  card?: Card;
  media_attachments?: MediaAttachment[];
  reblog?: Post;
  quote?: Post;
  post_type?: string;
  topics?: string[];
  vibes?: { primary?: string; scores?: Record<string, number> };
  duration?: number;
  podcast?: boolean;
  paywall?: boolean;
  orientation?: string;
  /** Longform document summary, present when the post links to a standard.site / Leaflet document. */
  document?: DocumentSummary;
}

/** URL resolution result. */
export interface ResolveResult {
  input_url: string;
  final_url: string;
  status: number;
  chain: string[];
}

/** Topics result for a URL. */
export interface TopicsResult {
  url: string;
  topics: Topic[];
  tags: string[];
  post_types: string[];
  language?: string;
}

/** OAuth-authorized third-party app. */
export interface ConnectedApp {
  authorization_id: number;
  app_id: string;
  app_name: string;
  logo_url?: string;
  scopes: string;
  authorized_at: string;
  last_used: string;
}

/** A longform publication (standard.site / Leaflet). */
export interface Publication {
  /** Publication AT-URI. */
  uri: string;
  name?: string;
  description?: string;
  icon_url?: string;
  did?: string;
  publisher_handle?: string;
  publisher_display_name?: string;
  publisher_avatar?: string;
}

/** A longform document (standard.site / Leaflet). */
export interface Document {
  /** Document AT-URI. */
  id: string;
  title?: string;
  description?: string;
  published_at?: string;
  path?: string;
  cover_image_url?: string;
  tags?: string[];
  publication_uri?: string;
  publication?: Publication;
  author?: { did: string; handle?: string };
  comments_count: number;
  /** Rendered HTML content — present when fetched with format 'html' (the default). */
  content_html?: string;
  /** Raw block pages — present when fetched with format 'blocks'. */
  pages?: unknown[];
}

/**
 * Compact document summary attached as `document` on longform posts in feed and
 * search responses. (Publication document listings use PublicationDocumentEntry.)
 */
export interface DocumentSummary {
  title?: string;
  description?: string;
  cover_image_url?: string;
  tags?: string[];
  publication_uri?: string;
}

/** Entry in a publication's document listing. */
export interface PublicationDocumentEntry {
  /** Document AT-URI. */
  uri: string;
  title?: string;
  description?: string;
  path?: string;
  cover_image_url?: string;
  published_at?: string;
  tags?: string[];
}

/** Post enrichment data. */
export interface EnrichmentData {
  post_id: string;
  topics?: Topic[];
  post_types?: string[];
  language?: string;
  nsfw?: boolean;
  claim_score?: number;
  tags?: string[];
  contains_url?: boolean;
  flus_url?: string;
  flus_domain?: string;
  domain_boost?: number;
  duration?: number;
  podcast?: boolean;
  orientation?: string;
  paywall?: boolean;
  favourites_count?: number;
  reblogs_count?: number;
  replies_count?: number;
  [key: string]: unknown;
}

// ==========================================================================
// Podcast intelligence (episode search, guests, mentions, sponsors, show notes)
// ==========================================================================

/** One transcript chunk matching a semantic podcast episode search. */
export interface PodcastEpisodeSearchResult {
  /** The episode's audio/enclosure URL. */
  episode_url: string;
  /** SHA1 hex of the full audio URL — the episode's stable ID across the audio APIs. */
  episode_url_hash: string;
  /** Podcast feed ID (SHA1 hex of the full RSS feed URL). */
  flyf_id?: string | null;
  podcast_name?: string | null;
  episode_title?: string | null;
  /** Semantic similarity score (0-1, higher is better). */
  score: number;
  /** Start of the matching transcript chunk, in seconds. */
  chunk_start_seconds?: number | null;
  /** End of the matching transcript chunk, in seconds. */
  chunk_end_seconds?: number | null;
  /** Text preview of the matching transcript chunk. */
  preview?: string | null;
}

/** Response of `audio.searchPodcastEpisodes`. */
export interface PodcastEpisodeSearchResponse {
  ok: boolean;
  /** Echo of the search query. */
  query: string;
  /** Echo of the podcast filter, if any. */
  flyf_id?: string | null;
  results: PodcastEpisodeSearchResult[];
  /** Number of results returned. */
  total: number;
}

/** One detected episode appearance of a podcast guest or host. */
export interface PodcastGuestAppearance {
  /** Podcast feed ID (SHA1 hex of the full RSS feed URL). */
  flyf_id?: string | null;
  podcast_name?: string | null;
  episode_url: string;
  /** SHA1 hex of the full audio URL. */
  episode_url_hash: string;
  /** Detected role in the episode (e.g. 'host', 'guest'). */
  role?: string | null;
  /** Detection confidence (0-1). */
  confidence?: number | null;
  speaking_time_seconds?: number | null;
  detected_at?: string | null;
}

/** A podcast guest or host detected via transcript and speaker analysis. */
export interface PodcastGuest {
  name: string;
  /** Professional title, when known (e.g. 'CEO'). */
  title?: string | null;
  organization?: string | null;
  bluesky_handle?: string | null;
  mastodon_handle?: string | null;
  /** Episodes this person appeared in, newest first. */
  appearances: PodcastGuestAppearance[];
}

/** Response of `audio.searchPodcastGuests`. */
export interface PodcastGuestSearchResponse {
  ok: boolean;
  /** Echo of the search query. */
  query: string;
  guests: PodcastGuest[];
  /** Number of guests returned. */
  total: number;
}

/** All mentions of one entity within one episode. */
export interface PodcastMention {
  episode_url: string;
  /** SHA1 hex of the full audio URL. */
  episode_url_hash: string;
  /** Podcast feed ID (SHA1 hex of the full RSS feed URL). */
  flyf_id?: string | null;
  /** Entity name as spoken/recognized (original casing). */
  entity: string;
  entity_type: 'person' | 'organization' | 'location';
  /** Number of times the entity is mentioned in the episode. */
  mention_count: number;
  /** Time of the first mention, in seconds. */
  first_start_seconds?: number | null;
  /** Mention time ranges (up to 50 per episode), in seconds. */
  timestamps: Array<{ start: number; end: number }>;
  /** When the episode was indexed. */
  created_at?: string | null;
}

/** Response of `audio.getPodcastMentions`. */
export interface PodcastMentionsResponse {
  ok: boolean;
  /** Normalized (lowercased) entity name that was matched. */
  entity: string;
  entity_type?: string | null;
  flyf_id?: string | null;
  mentions: PodcastMention[];
  /** Number of rows returned (page size, not the global count). */
  total: number;
  limit: number;
  offset: number;
}

/** One classified podcast ad placement in one episode. */
export interface PodcastSponsorAd {
  episode_url: string;
  /** SHA1 hex of the full audio URL. */
  episode_url_hash: string;
  /** Podcast feed ID (SHA1 hex of the full RSS feed URL). */
  flyf_id?: string | null;
  /** Advertiser company name. */
  company: string;
  /** Advertised product or service. */
  product?: string | null;
  /** Advertiser category (e.g. 'technology', 'finance', 'health'). */
  category?: string | null;
  /** Ad format (e.g. 'host_read', 'produced'). */
  ad_format?: string | null;
  /** Promo code offered in the ad, when present. */
  promo_code?: string | null;
  /** Ad start time in the episode, in seconds. */
  start_seconds?: number | null;
  end_seconds?: number | null;
  duration_seconds?: number | null;
  /** Ad detection confidence (0-1). */
  confidence?: number | null;
  /** Preview of the transcribed ad read (up to 1024 chars). */
  ad_text_preview?: string | null;
  /** Version of the classification model that produced this row. */
  model_version?: string | null;
  /** When the ad was detected and classified. */
  created_at?: string | null;
}

/** Response of `audio.getPodcastSponsors`. */
export interface PodcastSponsorsResponse {
  ok: boolean;
  /** Normalized (lowercased) company name that was matched. */
  company?: string | null;
  episode_url_hash?: string | null;
  flyf_id?: string | null;
  sponsors: PodcastSponsorAd[];
  /** Number of rows returned (page size, not the global count). */
  total: number;
  limit: number;
  offset: number;
}

/** AI-generated structured show notes for a transcribed episode. */
export interface PodcastShowNotes {
  episode_url?: string;
  /** SHA1 hex of the full audio URL (language-suffixed for translations). */
  episode_url_hash?: string;
  /** One-paragraph episode summary. */
  summary?: string | null;
  show_notes?: {
    description?: string;
    topics?: string[];
    people?: string[];
    organizations?: string[];
    /** Timestamped outline of the episode ('HH:MM:SS' labels). */
    timestamps?: Array<{ time?: string; description?: string }>;
    /** Links and resources mentioned in the episode. */
    resources?: string[];
  } | null;
  takeaways?: Array<{ text?: string; category?: string | null }> | null;
  chapters?: Array<{
    title?: string;
    /** Chapter start in seconds. */
    start_time?: number;
    end_time?: number | null;
    summary?: string | null;
  }> | null;
  status?: 'ready' | 'processing';
}

/** Response of `audio.getShowNotes`. */
export interface ShowNotesResponse {
  showNotes?: PodcastShowNotes;
  /** Signed URL for the raw show-notes JSON (valid for 1 hour). */
  signed_url?: string;
  status?: 'ready';
}

// ==========================================================================
// Podcast intelligence — phase 4 (fact checks, translations, catch-up, topic seek)
// ==========================================================================

/** One fact-checked claim from a podcast episode. */
export interface PodcastFactCheck {
  /** Position of the claim within the episode's fact checks (0-based). */
  claim_index: number;
  /** The claim as extracted from the transcript. */
  claim_text: string;
  /** Kind of claim (e.g. 'statistic', 'event', 'quote'). */
  claim_type?: string | null;
  /** Where the claim is made in the episode, in seconds. */
  timestamp_seconds?: number | null;
  /** Fact-check verdict (e.g. 'verified', 'disputed', 'false', 'unverifiable'). */
  verdict: string;
  /** Verdict confidence (0-1). */
  confidence?: number | null;
  /** Short explanation of the verdict. */
  explanation?: string | null;
  /** Source citations backing the verdict. */
  sources: Array<Record<string, unknown>>;
  /** Web searches run while checking the claim. */
  search_queries: string[];
}

/** Response of `audio.getFactChecks`. */
export interface PodcastFactChecksResponse {
  ok: boolean;
  /** Echo of the episode URL. */
  episode_url: string;
  /** Fact-checked claims, in claim order. */
  fact_checks: PodcastFactCheck[];
  /** Number of claims returned. */
  total: number;
  /** Claim count per verdict (e.g. verified, disputed). */
  summary?: Record<string, number> | null;
  error?: string | null;
}

/** A stored transcript translation for one episode and language. */
export interface PodcastTranslation {
  /** Detected language of the original transcript. */
  source_language?: string | null;
  target_language?: string | null;
  /** The full translated transcript text. */
  translated_transcript: string;
  /** Timestamped translated segments. */
  translated_segments: Array<Record<string, unknown>>;
  /** Translated TTS audio URL, when audio was generated. */
  audio_url?: string | null;
  audio_duration_seconds?: number | null;
  /** Voice used for the translated audio. */
  tts_voice?: string | null;
  word_count?: number | null;
  original_duration_seconds?: number | null;
}

/** Response of `audio.getTranslation`. */
export interface PodcastTranslationResponse {
  ok: boolean;
  /** Echo of the episode URL. */
  episode_url: string;
  /** Echo of the requested language. */
  language: string;
  /** Null when no stored translation exists (the endpoint then 404s). */
  translation: PodcastTranslation | null;
  error?: string | null;
}

/** Response of `audio.getCatchUp`. */
export interface PodcastCatchUpResponse {
  ok: boolean;
  /** Echo of the episode URL. */
  episode_url: string;
  /** Echo of the requested playback position, in seconds. */
  timestamp_seconds: number;
  /** Prose summary of everything before the timestamp. */
  summary?: string | null;
  topics_covered: string[];
  key_points: string[];
  /** How much episode time the summary covers, in seconds. */
  missed_duration_seconds?: number | null;
  error?: string | null;
}

/** One transcript passage matching a skip-to-topic query. */
export interface PodcastTopicMatch {
  /** Passage start time, in seconds. */
  start_seconds?: number | null;
  /** Passage end time, in seconds. */
  end_seconds?: number | null;
  /** Preview of the matching transcript passage. */
  text_preview?: string | null;
  /** Relevance score (higher is more relevant). */
  score?: number | null;
}

/** Response of `audio.skipToTopic`. */
export interface PodcastTopicSeekResponse {
  ok: boolean;
  /** Echo of the episode URL. */
  episode_url: string;
  /** Echo of the requested topic. */
  topic: string;
  /** Matching passages, best first. Empty with `ok: true` means nothing scored above the relevance floor. */
  matches: PodcastTopicMatch[];
  /** Number of matches returned. */
  total: number;
  error?: string | null;
}
