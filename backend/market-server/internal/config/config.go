package config

import (
	"fmt"
	"os"
	"strings"
)

// RedisConfig Redis 연결 설정
type RedisConfig struct {
	Host     string
	Port     string
	Password string
}

// KISConfig 한국투자증권 OpenAPI 설정 (단일 키 세트)
type KISConfig struct {
	AppKey    string
	AppSecret string
	BaseURL   string
	WSURL     string // 체결가/호가 모두 단일 연결로 처리
}

// MySQLConfig MySQL 연결 설정
type MySQLConfig struct {
	Host     string
	Port     string
	User     string
	Password string
	DBName   string
}

// ServerConfig HTTP 서버 설정
type ServerConfig struct {
	Port string
}

// KafkaConfig Kafka 브로커 및 토픽 설정
type KafkaConfig struct {
	Brokers        []string
	TickTopic      string
	OrderbookTopic string
}

type Config struct {
	MySQL  MySQLConfig
	Redis  RedisConfig
	KIS    []KISConfig // 다중 API Key 지원 (키 수만큼 WebSocket 세션 생성)
	Server ServerConfig
	Kafka  KafkaConfig
}

// Load 환경변수에서 설정을 읽어 Config를 반환한다. 값이 없으면 기본값을 사용한다.
func Load() *Config {
	return &Config{
		MySQL: MySQLConfig{
			Host:     getEnvOrDefault("DB_HOST", "localhost"),
			Port:     getEnvOrDefault("DB_PORT", "3306"),
			User:     getEnvOrDefault("DB_USER", "root"),
			Password: os.Getenv("DB_PASSWORD"),
			DBName:   getEnvOrDefault("DB_NAME", "stock_db"),
		},
		Redis: RedisConfig{
			Host:     getEnvOrDefault("REDIS_HOST", "localhost"),
			Port:     getEnvOrDefault("REDIS_PORT", "6379"),
			Password: os.Getenv("REDIS_PASSWORD"),
		},
		KIS:    loadKISConfigs(),
		Server: ServerConfig{
			Port: getEnvOrDefault("SERVER_PORT", "8085"),
		},
		Kafka: KafkaConfig{
			Brokers:        getKafkaBrokers(),
			TickTopic:      getEnvOrDefault("KAFKA_TICK_TOPIC", "market.tick"),
			OrderbookTopic: getEnvOrDefault("KAFKA_ORDERBOOK_TOPIC", "market.orderbook"),
		},
	}
}

// loadKISConfigs KIS_APP_KEY_1 ~ KIS_APP_KEY_N 환경변수를 순서대로 읽어 []KISConfig를 반환한다.
// 번호가 빠진 시점에서 로딩을 중단한다 (예: 1,2,3 존재 시 3개 반환).
// 하위호환: 번호 없는 KIS_APP_KEY도 단일 키로 지원한다.
func loadKISConfigs() []KISConfig {
	baseURL := getEnvOrDefault("KIS_BASE_URL", "https://openapivts.koreainvestment.com:29443")
	wsURL := getEnvOrDefault("KIS_WS_URL", "ws://ops.koreainvestment.com:31000/tryitout/H0STCNT0")

	var configs []KISConfig

	// 번호 붙은 키 탐색 (KIS_APP_KEY_1, KIS_APP_KEY_2, ...)
	for i := 1; i <= 10; i++ { // 최대 10개까지 탐색
		key := os.Getenv(fmt.Sprintf("KIS_APP_KEY_%d", i))
		secret := os.Getenv(fmt.Sprintf("KIS_APP_SECRET_%d", i))
		if key == "" || secret == "" {
			break // 연속된 번호가 끊기면 중단
		}
		configs = append(configs, KISConfig{
			AppKey:    key,
			AppSecret: secret,
			BaseURL:   baseURL,
			WSURL:     wsURL,
		})
	}

	// 번호 붙은 키가 하나도 없으면 기존 KIS_APP_KEY / KIS_APP_SECRET 하위호환
	if len(configs) == 0 {
		key := os.Getenv("KIS_APP_KEY")
		secret := os.Getenv("KIS_APP_SECRET")
		if key != "" && secret != "" {
			configs = append(configs, KISConfig{
				AppKey:    key,
				AppSecret: secret,
				BaseURL:   baseURL,
				WSURL:     wsURL,
			})
		}
	}

	return configs
}

// getEnvOrDefault 환경변수가 없으면 defaultVal을 반환한다.
func getEnvOrDefault(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

func getKafkaBrokers() []string {
	if brokers := strings.TrimSpace(os.Getenv("KAFKA_BOOTSTRAP_SERVERS")); brokers != "" {
		return splitAndTrim(brokers)
	}
	if broker := strings.TrimSpace(os.Getenv("KAFKA_BROKER")); broker != "" {
		return []string{broker}
	}
	return []string{"localhost:9092"}
}

func splitAndTrim(value string) []string {
	parts := strings.Split(value, ",")
	brokers := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			brokers = append(brokers, trimmed)
		}
	}
	if len(brokers) == 0 {
		return []string{"localhost:9092"}
	}
	return brokers
}
