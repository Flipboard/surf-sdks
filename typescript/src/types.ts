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
