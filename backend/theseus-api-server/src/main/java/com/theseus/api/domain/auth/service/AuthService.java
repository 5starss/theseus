package com.theseus.api.domain.auth.service;

import com.theseus.api.common.exception.CustomException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.dto.request.LoginRequest;
import com.theseus.api.domain.auth.dto.response.LoginResponse;
import com.theseus.api.domain.auth.dto.response.LoginResult;
import com.theseus.api.domain.auth.dto.response.TokenReissueResponse;
import com.theseus.api.domain.auth.entity.RefreshToken;
import com.theseus.api.domain.auth.repository.RefreshTokenRepository;
import com.theseus.api.domain.auth.token.JwtTokenProvider;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import io.jsonwebtoken.JwtException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HexFormat;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class AuthService {

	private static final String TOKEN_TYPE = "Bearer";
	private static final String HASH_ALGORITHM = "SHA-256";

	private final UserRepository userRepository;
	private final RefreshTokenRepository refreshTokenRepository;
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
	public TokenReissueResponse reissueAccessToken(String refreshToken) {
		RefreshToken savedRefreshToken = getSavedRefreshToken(refreshToken);
		validateRefreshToken(refreshToken, savedRefreshToken);
		String accessToken = jwtTokenProvider.createAccessToken(savedRefreshToken.getUser());

		return TokenReissueResponse.builder()
			.tokenType(TOKEN_TYPE)
			.accessToken(accessToken)
			.build();
	}

	@Transactional
	public void logout(String refreshToken) {
		if (refreshToken == null || refreshToken.isBlank()) {
			return;
		}

		refreshTokenRepository.deleteByTokenHash(hashToken(refreshToken));
	}

	private User findLoginUser(String loginId) {
		return userRepository.findByEmployeeNumber(loginId)
			.or(() -> userRepository.findByEmail(loginId))
			.orElseThrow(() -> new CustomException(ErrorCode.LOGIN_FAILED));
	}

	private void validatePassword(String password, User user) {
		if (!passwordEncoder.matches(password, user.getPassword())) {
			throw new CustomException(ErrorCode.LOGIN_FAILED);
		}
	}

	private String issueRefreshToken(User user) {
		String refreshToken = jwtTokenProvider.createRefreshToken(user);
		String tokenHash = hashToken(refreshToken);
		LocalDateTime expiresAt = LocalDateTime.now()
			.plus(Duration.ofMillis(jwtTokenProvider.getRefreshTokenExpirationMillis()));

		refreshTokenRepository.findByUser(user)
			.ifPresentOrElse(
				savedRefreshToken -> savedRefreshToken.update(tokenHash, expiresAt),
				() -> refreshTokenRepository.save(RefreshToken.builder()
					.user(user)
					.tokenHash(tokenHash)
					.expiresAt(expiresAt)
					.build())
			);

		return refreshToken;
	}

	private RefreshToken getSavedRefreshToken(String refreshToken) {
		if (refreshToken == null || refreshToken.isBlank()) {
			throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
		}

		return refreshTokenRepository.findByTokenHash(hashToken(refreshToken))
			.orElseThrow(() -> new CustomException(ErrorCode.INVALID_REFRESH_TOKEN));
	}

	private void validateRefreshToken(String refreshToken, RefreshToken savedRefreshToken) {
		if (savedRefreshToken.isExpired(LocalDateTime.now())) {
			refreshTokenRepository.delete(savedRefreshToken);
			throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
		}

		try {
			jwtTokenProvider.validateRefreshToken(refreshToken);
			Long tokenUserId = jwtTokenProvider.getUserId(refreshToken);

			if (!savedRefreshToken.getUser().getId().equals(tokenUserId)) {
				refreshTokenRepository.delete(savedRefreshToken);
				throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
			}
		} catch (JwtException | IllegalArgumentException exception) {
			throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN, exception);
		}
	}

	private String hashToken(String token) {
		try {
			MessageDigest messageDigest = MessageDigest.getInstance(HASH_ALGORITHM);
			byte[] digest = messageDigest.digest(token.getBytes(StandardCharsets.UTF_8));

			return HexFormat.of().formatHex(digest);
		} catch (NoSuchAlgorithmException exception) {
			throw new CustomException(ErrorCode.INTERNAL_SERVER_ERROR, exception);
		}
	}
}
