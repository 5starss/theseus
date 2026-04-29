package com.theseus.api.domain.auth.token;

import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JwtTokenProviderTest {

	private static final String SECRET = "theseus-local-development-jwt-secret-key-must-be-changed";
	private static final long ACCESS_TOKEN_EXPIRATION_MILLIS = 3_600_000L;
	private static final long REFRESH_TOKEN_EXPIRATION_MILLIS = 1_209_600_000L;

	private final JwtTokenProvider jwtTokenProvider = new JwtTokenProvider(
		SECRET,
		ACCESS_TOKEN_EXPIRATION_MILLIS,
		REFRESH_TOKEN_EXPIRATION_MILLIS
	);

	@Test
	@DisplayName("access token은 발급할 때마다 고유한 식별자를 가진다")
	void createAccessTokenCreatesUniqueToken() {
		// Given
		User user = createUser();

		// When
		String firstAccessToken = jwtTokenProvider.createAccessToken(user);
		String secondAccessToken = jwtTokenProvider.createAccessToken(user);

		// Then
		assertThat(firstAccessToken).isNotEqualTo(secondAccessToken);
	}

	@Test
	@DisplayName("refresh token은 발급할 때마다 고유한 식별자를 가진다")
	void createRefreshTokenCreatesUniqueToken() {
		// Given
		User user = createUser();

		// When
		String firstRefreshToken = jwtTokenProvider.createRefreshToken(user);
		String secondRefreshToken = jwtTokenProvider.createRefreshToken(user);

		// Then
		assertThat(firstRefreshToken).isNotEqualTo(secondRefreshToken);
	}

	@Test
	@DisplayName("refresh token은 access token으로 인증할 수 없다")
	void validateTokenRejectsRefreshToken() {
		// Given
		User user = createUser();
		String refreshToken = jwtTokenProvider.createRefreshToken(user);

		// When & Then
		assertThatThrownBy(() -> jwtTokenProvider.validateToken(refreshToken))
			.isInstanceOf(IllegalArgumentException.class);
	}

	@Test
	@DisplayName("access token은 refresh token으로 재발급에 사용할 수 없다")
	void validateRefreshTokenRejectsAccessToken() {
		// Given
		User user = createUser();
		String accessToken = jwtTokenProvider.createAccessToken(user);

		// When & Then
		assertThatThrownBy(() -> jwtTokenProvider.validateRefreshToken(accessToken))
			.isInstanceOf(IllegalArgumentException.class);
	}

	private User createUser() {
		return User.builder()
			.employeeNumber("A001")
			.name("테스트 사용자")
			.email("test@example.com")
			.password("encoded-password")
			.systemRole(SystemRole.USER)
			.build();
	}
}
