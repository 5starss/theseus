package com.theseus.api.domain.auth.service;

import com.theseus.api.common.exception.CustomException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.dto.request.LoginRequest;
import com.theseus.api.domain.auth.dto.response.LoginResponse;
import com.theseus.api.domain.auth.token.JwtTokenProvider;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
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
	private final PasswordEncoder passwordEncoder;
	private final JwtTokenProvider jwtTokenProvider;

	public LoginResponse login(LoginRequest request) {
		User user = findLoginUser(request.getLoginId());
		validatePassword(request.getPassword(), user);
		String accessToken = jwtTokenProvider.createAccessToken(user);

		return LoginResponse.builder()
			.tokenType(TOKEN_TYPE)
			.accessToken(accessToken)
			.userId(user.getId())
			.name(user.getName())
			.systemRole(user.getSystemRole())
			.build();
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
}
