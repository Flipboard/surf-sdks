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
  /** Request timeout in ms (default: 30000) */
  timeout?: number;
  /** Custom fetch implementation (default: global fetch) */
  fetch?: typeof fetch;
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
