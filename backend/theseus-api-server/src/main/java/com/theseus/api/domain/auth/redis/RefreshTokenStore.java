package com.theseus.api.domain.auth.redis;

import java.time.Duration;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@RequiredArgsConstructor
@Component
public class RefreshTokenStore {

	private static final String KEY_PREFIX = "RT:";

	private final StringRedisTemplate stringRedisTemplate;

	public void save(Long userId, String refreshToken, Duration ttl) {
		stringRedisTemplate.opsForValue().set(buildKey(userId), refreshToken, ttl);
	}

	public Optional<String> findByUserId(Long userId) {
		return Optional.ofNullable(stringRedisTemplate.opsForValue().get(buildKey(userId)));
	}

	public void deleteByUserId(Long userId) {
		stringRedisTemplate.delete(buildKey(userId));
	}

	String buildKey(Long userId) {
		if (userId == null) {
			throw new IllegalArgumentException("userId must not be null.");
		}
		return KEY_PREFIX + userId;
	}
}
