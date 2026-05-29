/**
 * OAuth 2.0 Authorization Code Flow with PKCE for the Surf API.
 *
 * @example
 * ```ts
 * import { SurfOAuth } from '@surf/api/oauth';
 *
 * const oauth = new SurfOAuth({
 *   clientId: 'your-app-public-id',
 *   redirectUri: 'https://yourapp.com/callback',
 * });
 *
 * // Step 1: Generate authorization URL
 * const { url, state, codeVerifier } = oauth.getAuthorizeUrl({ scope: 'read:feeds write:statuses' });
 *
 * // Step 2: Exchange code after redirect
 * const tokens = await oauth.exchangeCode(code, codeVerifier);
 *
 * // Step 3: Use the access token
 * const client = new SurfClient({ apiKey: tokens.access_token });
 *
 * // Step 4: Refresh when expired
 * const newTokens = await oauth.refreshToken(tokens.refresh_token);
 * ```
 */

const DEFAULT_AUTH_URL = 'https://surf.social';
const DEFAULT_TOKEN_URL = 'https://surf.social/oauth/token';
const DEFAULT_REVOKE_URL = 'https://surf.social/oauth/revoke';

export interface SurfOAuthOptions {
  clientId: string;
  redirectUri: string;
  authBaseUrl?: string;
  tokenUrl?: string;
  revokeUrl?: string;
}

export interface AuthorizeUrlResult {
  url: string;
  state: string;
  codeVerifier: string;
}

export interface OAuthTokens {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
  scope: string;
}

/**
 * Generate a cryptographically secure random string.
 */
function randomString(length: number): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Generate PKCE code_verifier and code_challenge (S256).
 */
export async function generatePKCE(): Promise<{ verifier: string; challenge: string }> {
  const verifier = randomString(64);
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hash = await crypto.subtle.digest('SHA-256', data);
  const challenge = btoa(String.fromCharCode(...new Uint8Array(hash)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
  return { verifier, challenge };
}

export class SurfOAuth {
  private readonly clientId: string;
  private readonly redirectUri: string;
  private readonly authBaseUrl: string;
  private readonly tokenUrl: string;
  private readonly revokeUrl: string;

  constructor(options: SurfOAuthOptions) {
    this.clientId = options.clientId;
    this.redirectUri = options.redirectUri;
    this.authBaseUrl = (options.authBaseUrl ?? DEFAULT_AUTH_URL).replace(/\/+$/, '');
    this.tokenUrl = options.tokenUrl ?? DEFAULT_TOKEN_URL;
    this.revokeUrl = options.revokeUrl ?? DEFAULT_REVOKE_URL;
  }

  /**
   * Build the authorization URL with PKCE.
   * Returns the URL to redirect the user to, plus state and verifier to save.
   */
  async getAuthorizeUrl(options?: {
    scope?: string;
    state?: string;
  }): Promise<AuthorizeUrlResult> {
    const state = options?.state ?? randomString(32);
    const { verifier, challenge } = await generatePKCE();

    const params = new URLSearchParams({
      client_id: this.clientId,
      redirect_uri: this.redirectUri,
      scope: options?.scope ?? 'read:feeds',
      response_type: 'code',
      state,
      code_challenge: challenge,
      code_challenge_method: 'S256',
    });

    return {
      url: `${this.authBaseUrl}/oauth/authorize?${params.toString()}`,
      state,
      codeVerifier: verifier,
    };
  }

  /**
   * Exchange an authorization code for access + refresh tokens.
   */
  async exchangeCode(code: string, codeVerifier: string): Promise<OAuthTokens> {
    const resp = await fetch(this.tokenUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_type: 'authorization_code',
        client_id: this.clientId,
        code,
        redirect_uri: this.redirectUri,
        code_verifier: codeVerifier,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error_description ?? err.error ?? `Token exchange failed: ${resp.status}`);
    }
    return resp.json();
  }

  /**
   * Refresh an access token using a refresh token.
   * Note: refresh tokens rotate — the old one is invalidated.
   */
  async refreshToken(refreshToken: string): Promise<OAuthTokens> {
    const resp = await fetch(this.tokenUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_type: 'refresh_token',
        client_id: this.clientId,
        refresh_token: refreshToken,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error_description ?? err.error ?? `Token refresh failed: ${resp.status}`);
    }
    return resp.json();
  }

  /**
   * Revoke an access or refresh token.
   */
  async revoke(token: string): Promise<boolean> {
    const resp = await fetch(this.revokeUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: this.clientId,
        token,
      }),
    });
    return resp.ok;
  }
}
