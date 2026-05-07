package com.theseus.api.domain.auth.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.dto.request.LoginRequest;
import com.theseus.api.domain.auth.dto.response.LoginResponse;
import com.theseus.api.domain.auth.dto.response.LoginResult;
import com.theseus.api.domain.auth.dto.response.TokenReissueResponse;
import com.theseus.api.domain.auth.dto.response.TokenReissueResult;
import com.theseus.api.domain.auth.redis.RefreshTokenStore;
import com.theseus.api.domain.auth.token.JwtTokenProvider;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import io.jsonwebtoken.JwtException;
import java.time.Duration;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class AuthService {

	private static final String TOKEN_TYPE = "Bearer";

	private final UserRepository userRepository;
	private final RefreshTokenStore refreshTokenStore;
	private final PasswordEncoder passwordEncoder;
	private final JwtTokenProvider jwtTokenProvider;

	@Transactional
	public LoginResult login(LoginRequest request) {
		User user = findLoginUser(request.getLoginId());
		validatePassword(request.getPassword(), user);
		String accessToken = jwtTokenProvider.createAccessToken(user);
		String refreshToken = issueRefreshToken(user);

		LoginResponse response = LoginResponse.builder()
			.tokenType(TOKEN_TYPE)
			.accessToken(accessToken)
			.userId(user.getId())
			.name(user.getName())
			.systemRole(user.getSystemRole())
			.build();

		return new LoginResult(response, refreshToken);
	}

	@Transactional
	public TokenReissueResult reissueAccessToken(String refreshToken) {
		User user = validateAndFindRefreshTokenUser(refreshToken);
		String accessToken = jwtTokenProvider.createAccessToken(user);
		String newRefreshToken = issueRefreshToken(user);

		TokenReissueResponse response = TokenReissueResponse.builder()
			.tokenType(TOKEN_TYPE)
			.accessToken(accessToken)
			.build();

		return new TokenReissueResult(response, newRefreshToken);
	}

	@Transactional
	public void logout(String refreshToken) {
		if (refreshToken == null || refreshToken.isBlank()) {
			return;
		}

		try {
			jwtTokenProvider.validateRefreshToken(refreshToken);
			refreshTokenStore.deleteByUserId(jwtTokenProvider.getUserId(refreshToken));
		} catch (JwtException | IllegalArgumentException | BusinessException exception) {
			return;
		}
	}

	private User findLoginUser(String loginId) {
		return userRepository.findByEmployeeNumber(loginId)
			.or(() -> userRepository.findByEmail(loginId))
			.orElseThrow(() -> BusinessException.of(ErrorCode.LOGIN_FAILED));
	}

	private void validatePassword(String password, User user) {
		if (!passwordEncoder.matches(password, user.getPassword())) {
			throw BusinessException.of(ErrorCode.LOGIN_FAILED);
		}
	}

	private String issueRefreshToken(User user) {
		String refreshToken = jwtTokenProvider.createRefreshToken(user);
		refreshTokenStore.save(
			user.getId(),
			refreshToken,
			Duration.ofMillis(jwtTokenProvider.getRefreshTokenExpirationMillis())
		);

		return refreshToken;
	}

	private User validateAndFindRefreshTokenUser(String refreshToken) {
		if (refreshToken == null || refreshToken.isBlank()) {
			throw BusinessException.of(ErrorCode.INVALID_REFRESH_TOKEN);
		}

		try {
			jwtTokenProvider.validateRefreshToken(refreshToken);
			Long tokenUserId = jwtTokenProvider.getUserId(refreshToken);
			String savedRefreshToken = refreshTokenStore.findByUserId(tokenUserId)
				.orElseThrow(() -> BusinessException.of(ErrorCode.INVALID_REFRESH_TOKEN));

			if (!savedRefreshToken.equals(refreshToken)) {
				refreshTokenStore.deleteByUserId(tokenUserId);
				throw BusinessException.of(ErrorCode.INVALID_REFRESH_TOKEN);
			}

			return userRepository.findById(tokenUserId)
				.orElseThrow(() -> BusinessException.of(ErrorCode.INVALID_REFRESH_TOKEN));
		} catch (JwtException | IllegalArgumentException | BusinessException exception) {
			throw BusinessException.of(ErrorCode.INVALID_REFRESH_TOKEN, exception);
		}
	}
}
