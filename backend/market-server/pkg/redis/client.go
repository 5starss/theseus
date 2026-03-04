package redis

import (
	"context"
	"fmt"

	"github.com/redis/go-redis/v9"
	"market-server/internal/config"
)

// NewClient Redis 클라이언트를 생성하고 Ping으로 연결을 검증한다.
func NewClient(cfg config.RedisConfig) (*redis.Client, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.Host, cfg.Port),
		Password: cfg.Password,
		DB:       0,
	})

	if err := rdb.Ping(context.Background()).Err(); err != nil {
		return nil, fmt.Errorf("redis ping failed: %w", err)
	}

	return rdb, nil
}
