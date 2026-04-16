package kis

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"market-server/internal/config"
)

// Client KIS OpenAPI HTTP 클라이언트. OAuth2 액세스 토큰을 내부적으로 캐싱한다.
type Client struct {
	httpClient *http.Client
	cfg        config.KISConfig
	mu         sync.RWMutex // token/tokenExp 동시 접근 보호
	token      string
	tokenExp   time.Time
}

func NewClient(cfg config.KISConfig) *Client {
	return &Client{
		httpClient: &http.Client{Timeout: 10 * time.Second},
		cfg:        cfg,
	}
}

// tokenResponse KIS OAuth2 토큰 발급 응답
type tokenResponse struct {
	AccessToken string `json:"access_token"`
	ExpiresIn   int    `json:"expires_in"`
}

// getToken 유효한 액세스 토큰을 반환한다. 만료 1시간 전이면 자동 재발급한다.
func (c *Client) getToken(ctx context.Context) (string, error) {
	// 읽기 잠금으로 캐시 확인
	c.mu.RLock()
	// 만료 1시간 전 갱신
	if c.token != "" && time.Until(c.tokenExp) > time.Hour {
		token := c.token
		c.mu.RUnlock()
		return token, nil
	}
	c.mu.RUnlock()

	// 쓰기 잠금으로 재발급 (double-check: 다른 goroutine이 먼저 갱신했을 수 있음)
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.token != "" && time.Until(c.tokenExp) > time.Hour {
		return c.token, nil
	}

	body, _ := json.Marshal(map[string]string{
		"grant_type": "client_credentials",
		"appsecret":  c.cfg.AppSecret,
		"appkey":     c.cfg.AppKey,
	})

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.cfg.BaseURL+"/oauth2/tokenP", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("create token request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("token request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("token request status: %d", resp.StatusCode)
	}

	var tr tokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tr); err != nil {
		return "", fmt.Errorf("decode token response: %w", err)
	}

	c.token = tr.AccessToken
	c.tokenExp = time.Now().Add(time.Duration(tr.ExpiresIn) * time.Second)

	return c.token, nil
}

// StartTokenWorker 백그라운드에서 토큰을 주기적으로 갱신한다.
func (c *Client) StartTokenWorker(ctx context.Context) {
	// 최초 토큰 발급 시도
	_, err := c.getToken(ctx)
	if err != nil {
		fmt.Printf("KIS Token Init Error: %v\n", err)
	}

	ticker := time.NewTicker(10 * time.Minute) // 10분 주기 검사
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			// getToken 내부에서 만료 1시간 이내인지 확인 후 갱신
			_, err := c.getToken(ctx)
			if err != nil {
				fmt.Printf("KIS Token Renew Error: %v\n", err)
			}
		}
	}
}

// DoRequest 토큰을 자동 주입하여 KIS OpenAPI에 HTTP 요청을 보낸다. (429 Rate Limit 지수 백오프 적용)
func (c *Client) DoRequest(ctx context.Context, method, path string, headers map[string]string, query map[string]string) ([]byte, error) {
	token, err := c.getToken(ctx)
	if err != nil {
		return nil, fmt.Errorf("get token: %w", err)
	}

	const maxRetries = 3
	var backoff = 100 * time.Millisecond

	for attempt := 0; attempt <= maxRetries; attempt++ {
		req, err := http.NewRequestWithContext(ctx, method, c.cfg.BaseURL+path, nil)
		if err != nil {
			return nil, fmt.Errorf("create request: %w", err)
		}

		// KIS 필수 공통 헤더
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("appkey", c.cfg.AppKey)
		req.Header.Set("appsecret", c.cfg.AppSecret)
		req.Header.Set("Content-Type", "application/json; charset=utf-8")
		for k, v := range headers {
			req.Header.Set(k, v)
		}

		q := req.URL.Query()
		for k, v := range query {
			q.Set(k, v)
		}
		req.URL.RawQuery = q.Encode()

		resp, err := c.httpClient.Do(req)
		if err != nil {
			return nil, fmt.Errorf("do request: %w", err)
		}

		if resp.StatusCode == http.StatusTooManyRequests {
			resp.Body.Close()
			if attempt == maxRetries {
				return nil, fmt.Errorf("response status: 429 (rate limit exceeded after %d retries)", maxRetries)
			}
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
				backoff *= 2 // 지수 백오프 (Exponential Backoff)
				continue
			}
		}

		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("response status: %d", resp.StatusCode)
		}

		data, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("read response body: %w", err)
		}

		return data, nil
	}

	return nil, fmt.Errorf("max retries exceeded")
}
