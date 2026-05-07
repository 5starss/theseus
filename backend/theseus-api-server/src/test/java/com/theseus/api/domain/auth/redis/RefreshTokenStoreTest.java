package com.theseus.api.domain.auth.redis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Duration;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

@ExtendWith(MockitoExtension.class)
class RefreshTokenStoreTest {

	private static final Long USER_ID = 10L;
	private static final String KEY = "RT:10";

	@Mock
	private StringRedisTemplate stringRedisTemplate;

	@Mock
	private ValueOperations<String, String> valueOperations;

	private RefreshTokenStore refreshTokenStore;

	@BeforeEach
	void setUp() {
		refreshTokenStore = new RefreshTokenStore(stringRedisTemplate);
	}

	@Test
	@DisplayName("Refresh Token Redis key를 생성한다.")
	void buildKey() {
		assertThat(refreshTokenStore.buildKey(USER_ID)).isEqualTo(KEY);
	}

	@Test
	@DisplayName("Refresh Token을 사용자 ID key와 TTL로 저장한다.")
	void save() {
		when(stringRedisTemplate.opsForValue()).thenReturn(valueOperations);

		refreshTokenStore.save(USER_ID, "refresh-token", Duration.ofDays(14));

		verify(valueOperations).set(KEY, "refresh-token", Duration.ofDays(14));
	}

	@Test
	@DisplayName("사용자 ID로 Refresh Token을 조회한다.")
	void findByUserId() {
		when(stringRedisTemplate.opsForValue()).thenReturn(valueOperations);
		when(valueOperations.get(KEY)).thenReturn("refresh-token");

		Optional<String> found = refreshTokenStore.findByUserId(USER_ID);

		assertThat(found).contains("refresh-token");
	}

	@Test
	@DisplayName("사용자 ID로 Refresh Token을 삭제한다.")
	void deleteByUserId() {
		refreshTokenStore.deleteByUserId(USER_ID);

		verify(stringRedisTemplate).delete(KEY);
	}
}
