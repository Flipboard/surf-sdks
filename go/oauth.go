// Package surf provides OAuth 2.0 Authorization Code Flow with PKCE helpers.
//
// Usage:
//
//	oauth := surf.NewOAuth("client-id", "https://yourapp.com/callback")
//	url, state, verifier := oauth.GetAuthorizeURL("read:feeds write:statuses", "")
//	// redirect user to url, save state + verifier
//	tokens, err := oauth.ExchangeCode(code, verifier)
//	// use tokens.AccessToken with surf.NewClient()
package surf

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

const (
	defaultAuthBaseURL = "https://surf.social"
	defaultTokenURL    = "https://surf.social/oauth/token"
	defaultRevokeURL   = "https://surf.social/oauth/revoke"
)

// OAuthTokens holds the tokens returned from the authorization server.
type OAuthTokens struct {
	AccessToken  string `json:"access_token"`
	TokenType    string `json:"token_type"`
	ExpiresIn    int    `json:"expires_in"`
	RefreshToken string `json:"refresh_token"`
	Scope        string `json:"scope"`
}

// OAuth is a helper for the Surf OAuth 2.0 Authorization Code Flow with PKCE.
type OAuth struct {
	ClientID    string
	RedirectURI string
	AuthBaseURL string
	TokenURL    string
	RevokeURL   string
	HTTP        *http.Client
}

// NewOAuth creates a new OAuth helper with default URLs.
func NewOAuth(clientID, redirectURI string) *OAuth {
	return &OAuth{
		ClientID:    clientID,
		RedirectURI: redirectURI,
		AuthBaseURL: defaultAuthBaseURL,
		TokenURL:    defaultTokenURL,
		RevokeURL:   defaultRevokeURL,
		HTTP:        &http.Client{Timeout: 15 * time.Second},
	}
}

// GeneratePKCE generates a code_verifier and code_challenge (S256).
func GeneratePKCE() (verifier, challenge string) {
	b := make([]byte, 64)
	rand.Read(b)
	verifier = hex.EncodeToString(b)
	h := sha256.Sum256([]byte(verifier))
	challenge = base64.RawURLEncoding.EncodeToString(h[:])
	return
}

// GetAuthorizeURL builds the authorization URL with PKCE.
// If state is empty, a random state is generated.
// Returns (url, state, codeVerifier).
func (o *OAuth) GetAuthorizeURL(scope, state string) (string, string, string) {
	if state == "" {
		b := make([]byte, 32)
		rand.Read(b)
		state = hex.EncodeToString(b)
	}
	verifier, challenge := GeneratePKCE()

	params := url.Values{
		"client_id":             {o.ClientID},
		"redirect_uri":         {o.RedirectURI},
		"scope":                {scope},
		"response_type":        {"code"},
		"state":                {state},
		"code_challenge":       {challenge},
		"code_challenge_method": {"S256"},
	}
	return fmt.Sprintf("%s/oauth/authorize?%s", o.AuthBaseURL, params.Encode()), state, verifier
}

// ExchangeCode exchanges an authorization code for tokens.
func (o *OAuth) ExchangeCode(code, codeVerifier string) (*OAuthTokens, error) {
	body, err := json.Marshal(map[string]string{
		"grant_type":    "authorization_code",
		"client_id":     o.ClientID,
		"code":          code,
		"redirect_uri":  o.RedirectURI,
		"code_verifier": codeVerifier,
	})
	if err != nil {
		return nil, fmt.Errorf("marshal token request: %w", err)
	}
	resp, err := o.HTTP.Post(o.TokenURL, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read token response: %w", err)
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("token exchange failed (%d): %s", resp.StatusCode, string(data))
	}
	var tokens OAuthTokens
	if err := json.Unmarshal(data, &tokens); err != nil {
		return nil, err
	}
	return &tokens, nil
}

// RefreshToken uses a refresh token to get new tokens.
// Note: refresh tokens rotate — the old one is invalidated.
func (o *OAuth) RefreshToken(refreshToken string) (*OAuthTokens, error) {
	body, err := json.Marshal(map[string]string{
		"grant_type":    "refresh_token",
		"client_id":     o.ClientID,
		"refresh_token": refreshToken,
	})
	if err != nil {
		return nil, fmt.Errorf("marshal refresh request: %w", err)
	}
	resp, err := o.HTTP.Post(o.TokenURL, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read refresh response: %w", err)
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("token refresh failed (%d): %s", resp.StatusCode, string(data))
	}
	var tokens OAuthTokens
	if err := json.Unmarshal(data, &tokens); err != nil {
		return nil, err
	}
	return &tokens, nil
}

// Revoke revokes an access or refresh token.
func (o *OAuth) Revoke(token string) error {
	body, err := json.Marshal(map[string]string{
		"client_id": o.ClientID,
		"token":     token,
	})
	if err != nil {
		return fmt.Errorf("marshal revoke request: %w", err)
	}
	resp, err := o.HTTP.Post(o.RevokeURL, "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("revocation failed: %d", resp.StatusCode)
	}
	return nil
}
