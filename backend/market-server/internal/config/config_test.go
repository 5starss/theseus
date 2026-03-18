package config

import (
	"testing"
)

// setEnv는 테스트용 환경변수를 설정하고, 테스트 종료 시 삭제하는 클린업을 등록한다.
func setEnv(t *testing.T, key, value string) {
	t.Helper()
	t.Setenv(key, value)
}

// ─── loadKISConfigs ───────────────────────────────────────────────────────────

// TestLoadKISConfigs_MultipleNumberedKeys KIS_APP_KEY_1~N 형식의 복수 키를 순서대로 로딩한다.
func TestLoadKISConfigs_MultipleNumberedKeys(t *testing.T) {
	setEnv(t, "KIS_APP_KEY_1", "key-1")
	setEnv(t, "KIS_APP_SECRET_1", "secret-1")
	setEnv(t, "KIS_APP_KEY_2", "key-2")
	setEnv(t, "KIS_APP_SECRET_2", "secret-2")
	setEnv(t, "KIS_APP_KEY_3", "key-3")
	setEnv(t, "KIS_APP_SECRET_3", "secret-3")

	configs := loadKISConfigs()

	if len(configs) != 3 {
		t.Fatalf("expected 3 configs, got %d", len(configs))
	}
	for i, cfg := range configs {
		wantKey := "key-" + string(rune('1'+i))
		wantSecret := "secret-" + string(rune('1'+i))
		if cfg.AppKey != wantKey {
			t.Errorf("configs[%d].AppKey = %q, want %q", i, cfg.AppKey, wantKey)
		}
		if cfg.AppSecret != wantSecret {
			t.Errorf("configs[%d].AppSecret = %q, want %q", i, cfg.AppSecret, wantSecret)
		}
	}
}

// TestLoadKISConfigs_LegacyFallback 번호 없는 KIS_APP_KEY/KIS_APP_SECRET을 단일 설정으로 지원한다.
func TestLoadKISConfigs_LegacyFallback(t *testing.T) {
	setEnv(t, "KIS_APP_KEY", "legacy-key")
	setEnv(t, "KIS_APP_SECRET", "legacy-secret")

	configs := loadKISConfigs()

	if len(configs) != 1 {
		t.Fatalf("expected 1 config (legacy fallback), got %d", len(configs))
	}
	if configs[0].AppKey != "legacy-key" {
		t.Errorf("AppKey = %q, want %q", configs[0].AppKey, "legacy-key")
	}
	if configs[0].AppSecret != "legacy-secret" {
		t.Errorf("AppSecret = %q, want %q", configs[0].AppSecret, "legacy-secret")
	}
}

// TestLoadKISConfigs_NumberedKeysPreferredOverLegacy 번호 붙은 키가 있으면 레거시 키를 무시한다.
func TestLoadKISConfigs_NumberedKeysPreferredOverLegacy(t *testing.T) {
	setEnv(t, "KIS_APP_KEY_1", "numbered-key")
	setEnv(t, "KIS_APP_SECRET_1", "numbered-secret")
	setEnv(t, "KIS_APP_KEY", "legacy-key-should-be-ignored")
	setEnv(t, "KIS_APP_SECRET", "legacy-secret-should-be-ignored")

	configs := loadKISConfigs()

	if len(configs) != 1 {
		t.Fatalf("expected 1 config (numbered only), got %d", len(configs))
	}
	if configs[0].AppKey != "numbered-key" {
		t.Errorf("레거시 키가 우선 적용됨: AppKey = %q", configs[0].AppKey)
	}
}

// TestLoadKISConfigs_GapInNumbering 번호가 연속되지 않으면 끊기는 시점에서 로딩을 중단한다.
// KIS_APP_KEY_1, KIS_APP_KEY_2, KIS_APP_KEY_4 → 1,2만 로딩 (3 없음)
func TestLoadKISConfigs_GapInNumbering(t *testing.T) {
	setEnv(t, "KIS_APP_KEY_1", "k1")
	setEnv(t, "KIS_APP_SECRET_1", "s1")
	setEnv(t, "KIS_APP_KEY_2", "k2")
	setEnv(t, "KIS_APP_SECRET_2", "s2")
	// 3번 없음
	setEnv(t, "KIS_APP_KEY_4", "k4")
	setEnv(t, "KIS_APP_SECRET_4", "s4")

	configs := loadKISConfigs()

	if len(configs) != 2 {
		t.Fatalf("번호 공백(3 없음) 이전까지만 로딩되어야 함: want 2, got %d", len(configs))
	}
}

// TestLoadKISConfigs_NoKeys_ReturnsEmpty 환경변수가 없으면 빈 슬라이스를 반환한다.
func TestLoadKISConfigs_NoKeys_ReturnsEmpty(t *testing.T) {
	// 관련 환경변수가 설정되지 않은 깨끗한 환경 보장 (t.Setenv가 이미 rollback 처리)
	configs := loadKISConfigs()

	// 다른 테스트 환경에서 KIS_APP_KEY 등이 설정되어 있을 수 있으므로 결과가 0이거나 기존 값을 반영한다.
	// 여기서는 t.Setenv로 명시적으로 빈 값을 설정하여 확실히 0을 보장한다.
	t.Setenv("KIS_APP_KEY", "")
	t.Setenv("KIS_APP_SECRET", "")
	configs = loadKISConfigs()

	if len(configs) != 0 {
		t.Errorf("환경변수 없으면 빈 슬라이스여야 함, got %d", len(configs))
	}
}

// TestLoadKISConfigs_OnlyKeyNoSecret Secret 없으면 해당 번호는 무시된다.
func TestLoadKISConfigs_OnlyKeyNoSecret(t *testing.T) {
	setEnv(t, "KIS_APP_KEY_1", "k1")
	// KIS_APP_SECRET_1 미설정

	t.Setenv("KIS_APP_SECRET_1", "") // 명시적으로 빈 값

	configs := loadKISConfigs()

	if len(configs) != 0 {
		t.Errorf("Secret 없으면 로딩되면 안 됨, got %d", len(configs))
	}
}

// TestLoadKISConfigs_SharedURLs 모든 클라이언트가 동일한 BaseURL, WSURL을 공유한다.
func TestLoadKISConfigs_SharedURLs(t *testing.T) {
	setEnv(t, "KIS_APP_KEY_1", "k1")
	setEnv(t, "KIS_APP_SECRET_1", "s1")
	setEnv(t, "KIS_APP_KEY_2", "k2")
	setEnv(t, "KIS_APP_SECRET_2", "s2")
	setEnv(t, "KIS_BASE_URL", "https://custom-base.example.com")
	setEnv(t, "KIS_WS_URL", "wss://custom-ws.example.com/ws")

	configs := loadKISConfigs()

	if len(configs) != 2 {
		t.Fatalf("expected 2 configs, got %d", len(configs))
	}
	for i, cfg := range configs {
		if cfg.BaseURL != "https://custom-base.example.com" {
			t.Errorf("configs[%d].BaseURL = %q, want custom URL", i, cfg.BaseURL)
		}
		if cfg.WSURL != "wss://custom-ws.example.com/ws" {
			t.Errorf("configs[%d].WSURL = %q, want custom WS URL", i, cfg.WSURL)
		}
	}
}

// TestLoadKISConfigs_DefaultURLs 환경변수 없으면 기본 URL이 적용된다.
func TestLoadKISConfigs_DefaultURLs(t *testing.T) {
	setEnv(t, "KIS_APP_KEY_1", "k1")
	setEnv(t, "KIS_APP_SECRET_1", "s1")
	setEnv(t, "KIS_BASE_URL", "")
	setEnv(t, "KIS_WS_URL", "")

	configs := loadKISConfigs()

	if len(configs) != 1 {
		t.Fatalf("expected 1 config, got %d", len(configs))
	}
	if configs[0].BaseURL == "" {
		t.Error("BaseURL이 기본값으로 설정되어야 함")
	}
	if configs[0].WSURL == "" {
		t.Error("WSURL이 기본값으로 설정되어야 함")
	}
}

// TestLoadKISConfigs_MaxTenKeys 최대 10개까지만 탐색한다 (10개 이상은 무시).
func TestLoadKISConfigs_MaxTenKeys(t *testing.T) {
	for i := 1; i <= 10; i++ {
		setEnv(t, "KIS_APP_KEY_"+itoa(i), "k"+itoa(i))
		setEnv(t, "KIS_APP_SECRET_"+itoa(i), "s"+itoa(i))
	}

	configs := loadKISConfigs()

	if len(configs) != 10 {
		t.Errorf("expected 10 configs, got %d", len(configs))
	}
}

// ─── getKafkaBrokers ──────────────────────────────────────────────────────────

// TestGetKafkaBrokers_BootstrapServers KAFKA_BOOTSTRAP_SERVERS에서 복수 브로커를 파싱한다.
func TestGetKafkaBrokers_BootstrapServers(t *testing.T) {
	setEnv(t, "KAFKA_BOOTSTRAP_SERVERS", "broker1:9092,broker2:9092,broker3:9092")
	setEnv(t, "KAFKA_BROKER", "") // 우선순위 낮은 변수 비움

	brokers := getKafkaBrokers()

	if len(brokers) != 3 {
		t.Fatalf("expected 3 brokers, got %d: %v", len(brokers), brokers)
	}
	want := []string{"broker1:9092", "broker2:9092", "broker3:9092"}
	for i, b := range brokers {
		if b != want[i] {
			t.Errorf("brokers[%d] = %q, want %q", i, b, want[i])
		}
	}
}

// TestGetKafkaBrokers_BootstrapServersTrimmed 공백이 포함된 브로커 목록을 trim한다.
func TestGetKafkaBrokers_BootstrapServersTrimmed(t *testing.T) {
	setEnv(t, "KAFKA_BOOTSTRAP_SERVERS", "  broker1:9092 , broker2:9092 ")
	setEnv(t, "KAFKA_BROKER", "")

	brokers := getKafkaBrokers()

	if len(brokers) != 2 {
		t.Fatalf("expected 2 brokers, got %d", len(brokers))
	}
	if brokers[0] != "broker1:9092" || brokers[1] != "broker2:9092" {
		t.Errorf("공백 trim 실패: %v", brokers)
	}
}

// TestGetKafkaBrokers_SingleBroker KAFKA_BROKER 단일 브로커를 슬라이스로 반환한다.
func TestGetKafkaBrokers_SingleBroker(t *testing.T) {
	setEnv(t, "KAFKA_BOOTSTRAP_SERVERS", "")
	setEnv(t, "KAFKA_BROKER", "single-broker:9092")

	brokers := getKafkaBrokers()

	if len(brokers) != 1 {
		t.Fatalf("expected 1 broker, got %d", len(brokers))
	}
	if brokers[0] != "single-broker:9092" {
		t.Errorf("broker = %q, want %q", brokers[0], "single-broker:9092")
	}
}

// TestGetKafkaBrokers_BootstrapServersPreferredOverSingle KAFKA_BOOTSTRAP_SERVERS가 KAFKA_BROKER보다 우선한다.
func TestGetKafkaBrokers_BootstrapServersPreferredOverSingle(t *testing.T) {
	setEnv(t, "KAFKA_BOOTSTRAP_SERVERS", "priority-broker:9092")
	setEnv(t, "KAFKA_BROKER", "low-priority:9092")

	brokers := getKafkaBrokers()

	if len(brokers) != 1 || brokers[0] != "priority-broker:9092" {
		t.Errorf("KAFKA_BOOTSTRAP_SERVERS가 우선되어야 함: got %v", brokers)
	}
}

// TestGetKafkaBrokers_Default 환경변수 없으면 localhost:9092를 반환한다.
func TestGetKafkaBrokers_Default(t *testing.T) {
	setEnv(t, "KAFKA_BOOTSTRAP_SERVERS", "")
	setEnv(t, "KAFKA_BROKER", "")

	brokers := getKafkaBrokers()

	if len(brokers) != 1 || brokers[0] != "localhost:9092" {
		t.Errorf("기본 브로커가 localhost:9092여야 함, got %v", brokers)
	}
}

// ─── Load (통합) ──────────────────────────────────────────────────────────────

// TestLoad_DefaultValues 환경변수 없을 때 각 컴포넌트의 기본값이 설정된다.
func TestLoad_DefaultValues(t *testing.T) {
	// 모든 관련 env를 비워서 기본값만 확인
	for _, key := range []string{
		"DB_HOST", "DB_PORT", "DB_USER", "DB_NAME",
		"REDIS_HOST", "REDIS_PORT",
		"SERVER_PORT",
		"KAFKA_BOOTSTRAP_SERVERS", "KAFKA_BROKER",
		"KAFKA_TICK_TOPIC", "KAFKA_ORDERBOOK_TOPIC",
	} {
		setEnv(t, key, "")
	}

	cfg := Load()

	if cfg.MySQL.Host != "localhost" {
		t.Errorf("MySQL.Host default: got %q, want %q", cfg.MySQL.Host, "localhost")
	}
	if cfg.MySQL.Port != "3306" {
		t.Errorf("MySQL.Port default: got %q, want %q", cfg.MySQL.Port, "3306")
	}
	if cfg.Redis.Host != "localhost" {
		t.Errorf("Redis.Host default: got %q, want %q", cfg.Redis.Host, "localhost")
	}
	if cfg.Redis.Port != "6379" {
		t.Errorf("Redis.Port default: got %q, want %q", cfg.Redis.Port, "6379")
	}
	if cfg.Server.Port != "8085" {
		t.Errorf("Server.Port default: got %q, want %q", cfg.Server.Port, "8085")
	}
	if cfg.Kafka.TickTopic != "market.tick" {
		t.Errorf("Kafka.TickTopic default: got %q, want %q", cfg.Kafka.TickTopic, "market.tick")
	}
	if cfg.Kafka.OrderbookTopic != "market.orderbook" {
		t.Errorf("Kafka.OrderbookTopic default: got %q, want %q", cfg.Kafka.OrderbookTopic, "market.orderbook")
	}
}

// TestLoad_EnvOverridesDefaults 환경변수가 있으면 기본값보다 우선한다.
func TestLoad_EnvOverridesDefaults(t *testing.T) {
	setEnv(t, "DB_HOST", "custom-db-host")
	setEnv(t, "DB_PORT", "5432")
	setEnv(t, "REDIS_HOST", "custom-redis")
	setEnv(t, "SERVER_PORT", "9090")

	cfg := Load()

	if cfg.MySQL.Host != "custom-db-host" {
		t.Errorf("DB_HOST override failed: got %q", cfg.MySQL.Host)
	}
	if cfg.MySQL.Port != "5432" {
		t.Errorf("DB_PORT override failed: got %q", cfg.MySQL.Port)
	}
	if cfg.Redis.Host != "custom-redis" {
		t.Errorf("REDIS_HOST override failed: got %q", cfg.Redis.Host)
	}
	if cfg.Server.Port != "9090" {
		t.Errorf("SERVER_PORT override failed: got %q", cfg.Server.Port)
	}
}

// ─── getEnvOrDefault ──────────────────────────────────────────────────────────

func TestGetEnvOrDefault_ReturnsEnvWhenSet(t *testing.T) {
	setEnv(t, "TEST_KEY_UNIQUE_12345", "custom-value")
	got := getEnvOrDefault("TEST_KEY_UNIQUE_12345", "default")
	if got != "custom-value" {
		t.Errorf("got %q, want %q", got, "custom-value")
	}
}

func TestGetEnvOrDefault_ReturnsDefaultWhenEmpty(t *testing.T) {
	setEnv(t, "TEST_KEY_EMPTY_99999", "")
	got := getEnvOrDefault("TEST_KEY_EMPTY_99999", "fallback")
	if got != "fallback" {
		t.Errorf("got %q, want %q", got, "fallback")
	}
}

// ─── 헬퍼 ─────────────────────────────────────────────────────────────────────

// itoa는 fmt 없이 작은 정수를 문자열로 변환한다.
func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	b := make([]byte, 0, 3)
	for n > 0 {
		b = append([]byte{byte('0' + n%10)}, b...)
		n /= 10
	}
	return string(b)
}
