package config

import "os"

// RedisConfig Redis 연결 설정
type RedisConfig struct {
	Host     string
	Port     string
	Password string
}

// KISConfig 한국투자증권 OpenAPI 설정
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
	KIS    KISConfig
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
		KIS: KISConfig{
			AppKey:    os.Getenv("KIS_APP_KEY"),
			AppSecret: os.Getenv("KIS_APP_SECRET"),
			BaseURL:   getEnvOrDefault("KIS_BASE_URL", "https://openapivts.koreainvestment.com:29443"),
			WSURL:     getEnvOrDefault("KIS_WS_URL", "ws://ops.koreainvestment.com:31000/tryitout/H0STCNT0"),
		},
		Server: ServerConfig{
			Port: getEnvOrDefault("SERVER_PORT", "8085"),
		},
		Kafka: KafkaConfig{
			Brokers:        []string{getEnvOrDefault("KAFKA_BROKER", "localhost:9092")},
			TickTopic:      getEnvOrDefault("KAFKA_TICK_TOPIC", "market.tick"),
			OrderbookTopic: getEnvOrDefault("KAFKA_ORDERBOOK_TOPIC", "market.orderbook"),
		},
	}
}

// getEnvOrDefault 환경변수가 없으면 defaultVal을 반환한다.
func getEnvOrDefault(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}
