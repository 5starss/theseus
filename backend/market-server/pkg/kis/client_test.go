package kis

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"testing"
	"time"

	"market-server/internal/config"
)

// mockTransport는 Interface 기반(RoundTripper) 외부 종속성 Mocking을 위한 구조체
type mockTransport struct {
	roundTripFunc func(req *http.Request) (*http.Response, error)
}

func (m *mockTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	return m.roundTripFunc(req)
}

func TestClient_getToken(t *testing.T) {
	cfg := config.KISConfig{
		AppKey:    "test-key",
		AppSecret: "test-secret",
		BaseURL:   "http://mock-kis",
	}

	client := NewClient(cfg)

	// Mock Transport 주입: 외부 호출 격리
	client.httpClient.Transport = &mockTransport{
		roundTripFunc: func(req *http.Request) (*http.Response, error) {
			if req.URL.Path == "/oauth2/tokenP" {
				resp := tokenResponse{
					AccessToken: "mock-token-1234",
					ExpiresIn:   86400,
				}
				body, _ := json.Marshal(resp)
				return &http.Response{
					StatusCode: http.StatusOK,
					Body:       io.NopCloser(bytes.NewReader(body)),
				}, nil
			}
			return &http.Response{
				StatusCode: http.StatusNotFound,
				Body:       io.NopCloser(bytes.NewReader([]byte{})),
			}, nil
		},
	}

	ctx := context.Background()
	token, err := client.getToken(ctx)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if token != "mock-token-1234" {
		t.Fatalf("expected 'mock-token-1234', got '%s'", token)
	}

	// 캐싱 여부 평가 (RoundTrip이 다시 불리지 않음)
	client.httpClient.Transport = &mockTransport{
		roundTripFunc: func(req *http.Request) (*http.Response, error) {
			t.Fatal("should not be called due to caching")
			return nil, nil
		},
	}
	cachedToken, err := client.getToken(ctx)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if cachedToken != "mock-token-1234" {
		t.Fatalf("expected cached token, got %s", cachedToken)
	}
}

func TestClient_DoRequest_RateLimitRetry(t *testing.T) {
	cfg := config.KISConfig{
		AppKey:    "test-key",
		AppSecret: "test-secret",
		BaseURL:   "http://mock-kis",
	}

	client := NewClient(cfg)
	// 토큰 발급 단계 패스 (캐싱된 상태 모의)
	client.token = "mock-token-1234"
	client.tokenExp = time.Now().Add(24 * time.Hour)

	var tryCount int

	client.httpClient.Transport = &mockTransport{
		roundTripFunc: func(req *http.Request) (*http.Response, error) {
			tryCount++
			if tryCount <= 2 {
				// 429 Too Many Requests 발생 (첫 번째, 두 번째 시도)
				return &http.Response{
					StatusCode: http.StatusTooManyRequests,
					Body:       io.NopCloser(bytes.NewReader([]byte(`{"rt_cd":"1", "msg_cd":"EGW20000", "msg1":"Rate Limit Exceeded"}`))),
				}, nil
			}

			// 세 번째 시도 기 성공 응답 ("000660" SK하이닉스 예시 등 현실적인 코드 사용)
			respBody := `{"rt_cd":"0", "msg_cd":"1000", "msg1":"Success", "output": {"stck_prpr": "180000"}}`
			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(bytes.NewReader([]byte(respBody))),
			}, nil
		},
	}

	ctx := context.Background()

	// "000660" (SK하이닉스) 조회 테스트
	data, err := client.DoRequest(ctx, http.MethodGet, "/uapi/domestic-stock/v1/quotations/inquire-price", nil, map[string]string{
		"FID_COND_MRKT_DIV_CODE": "J",
		"FID_INPUT_ISCD":         "000660",
	})
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if tryCount != 3 {
		t.Fatalf("expected 3 attempts due to retry logic, got %d", tryCount)
	}

	if !bytes.Contains(data, []byte("180000")) {
		t.Fatalf("unexpected response: %s", string(data))
	}
}
