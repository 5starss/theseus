package com.theseus.api.domain.auth.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.domain.auth.dto.response.TokenReissueResult;
import com.theseus.api.domain.auth.redis.RefreshTokenStore;
import com.theseus.api.domain.auth.token.JwtTokenProvider;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.Duration;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

	private static final Long USER_ID = 10L;
	private static final long REFRESH_TOKEN_EXPIRATION_MILLIS = 1_209_600_000L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private RefreshTokenStore refreshTokenStore;

	@Mock
	private PasswordEncoder passwordEncoder;

	@Mock
	private JwtTokenProvider jwtTokenProvider;

	private AuthService authService;

	@BeforeEach
	void setUp() {
		authService = new AuthService(
			userRepository,
			refreshTokenStore,
			passwordEncoder,
			jwtTokenProvider
		);
	}

	@Test
	@DisplayName("Redis에 저장된 Refresh Token과 쿠키 값이 같으면 토큰을 재발급하고 Refresh Token을 회전한다.")
	void reissueAccessTokenRotatesRefreshToken() {
		User user = createUser();
		when(jwtTokenProvider.validateRefreshToken("old-refresh-token")).thenReturn(true);
		when(jwtTokenProvider.getUserId("old-refresh-token")).thenReturn(USER_ID);
		when(refreshTokenStore.findByUserId(USER_ID)).thenReturn(Optional.of("old-refresh-token"));
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(jwtTokenProvider.createAccessToken(user)).thenReturn("new-access-token");
		when(jwtTokenProvider.createRefreshToken(user)).thenReturn("new-refresh-token");
		when(jwtTokenProvider.getRefreshTokenExpirationMillis()).thenReturn(REFRESH_TOKEN_EXPIRATION_MILLIS);

		TokenReissueResult result = authService.reissueAccessToken("old-refresh-token");

		assertThat(result.response().getTokenType()).isEqualTo("Bearer");
		assertThat(result.response().getAccessToken()).isEqualTo("new-access-token");
		assertThat(result.refreshToken()).isEqualTo("new-refresh-token");
		verify(refreshTokenStore).save(
			USER_ID,
			"new-refresh-token",
			Duration.ofMillis(REFRESH_TOKEN_EXPIRATION_MILLIS)
		);
	}

	@Test
	@DisplayName("쿠키 Refresh Token과 Redis 저장값이 다르면 Redis 값을 삭제하고 예외를 던진다.")
	void reissueAccessTokenRejectsMismatchedRefreshToken() {
		when(jwtTokenProvider.validateRefreshToken("cookie-refresh-token")).thenReturn(true);
		when(jwtTokenProvider.getUserId("cookie-refresh-token")).thenReturn(USER_ID);
		when(refreshTokenStore.findByUserId(USER_ID)).thenReturn(Optional.of("redis-refresh-token"));

		assertThatThrownBy(() -> authService.reissueAccessToken("cookie-refresh-token"))
			.isInstanceOf(BusinessException.class);
		verify(refreshTokenStore).deleteByUserId(USER_ID);
	}

	@Test
	@DisplayName("로그아웃 시 Refresh Token의 사용자 ID 기준으로 Redis key를 삭제한다.")
	void logoutDeletesRefreshTokenByUserId() {
		when(jwtTokenProvider.validateRefreshToken("refresh-token")).thenReturn(true);
		when(jwtTokenProvider.getUserId("refresh-token")).thenReturn(USER_ID);

		authService.logout("refresh-token");

		verify(refreshTokenStore).deleteByUserId(USER_ID);
	}

	private User createUser() {
		User user = User.builder()
			.employeeNumber("A001")
			.name("Auth User")
			.email("auth@example.com")
			.password("encoded-password")
			.systemRole(SystemRole.USER)
			.build();
		ReflectionTestUtils.setField(user, "id", USER_ID);
		return user;
	}
}
