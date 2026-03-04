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
}

// ServerConfig HTTP 서버 설정
type ServerConfig struct {
	Port string
}

type Config struct {
	Redis  RedisConfig
	KIS    KISConfig
	Server ServerConfig
}

// Load 환경변수에서 설정을 읽어 Config를 반환한다. 값이 없으면 기본값을 사용한다.
func Load() *Config {
	return &Config{
		Redis: RedisConfig{
			Host:     getEnvOrDefault("REDIS_HOST", "localhost"),
			Port:     getEnvOrDefault("REDIS_PORT", "6379"),
			Password: os.Getenv("REDIS_PASSWORD"),
		},
		KIS: KISConfig{
			AppKey:    os.Getenv("KIS_APP_KEY"),
			AppSecret: os.Getenv("KIS_APP_SECRET"),
			BaseURL:   getEnvOrDefault("KIS_BASE_URL", "https://openapi.koreainvestment.com:29443"),
		},
		Server: ServerConfig{
			Port: getEnvOrDefault("SERVER_PORT", "8085"),
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
