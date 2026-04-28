package com.theseus.api.domain.auth.service;

import com.theseus.api.domain.auth.dto.request.LoginRequest;
import com.theseus.api.domain.auth.dto.response.LoginResponse;
import com.theseus.api.domain.auth.token.JwtTokenProvider;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class AuthService {

	private static final String TOKEN_TYPE = "Bearer";
	private static final String LOGIN_FAILED_MESSAGE = "아이디 또는 비밀번호가 올바르지 않습니다.";

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
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, LOGIN_FAILED_MESSAGE));
	}

	private void validatePassword(String password, User user) {
		if (!passwordEncoder.matches(password, user.getPassword())) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, LOGIN_FAILED_MESSAGE);
		}
	}
}
