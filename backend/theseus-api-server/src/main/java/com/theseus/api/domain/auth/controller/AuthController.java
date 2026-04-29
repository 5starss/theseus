package com.theseus.api.domain.auth.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.cookie.RefreshTokenCookieProvider;
import com.theseus.api.domain.auth.dto.request.LoginRequest;
import com.theseus.api.domain.auth.dto.response.LoginResponse;
import com.theseus.api.domain.auth.dto.response.LoginResult;
import com.theseus.api.domain.auth.dto.response.TokenReissueResponse;
import com.theseus.api.domain.auth.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@Tag(name = "Auth", description = "인증 API")
@RequestMapping("/auth")
@RestController
public class AuthController {

	private final AuthService authService;
	private final RefreshTokenCookieProvider refreshTokenCookieProvider;

	@PostMapping("/login")
	@Operation(
		summary = "로그인",
		description = "사번 또는 이메일과 비밀번호를 검증하고, JWT access token과 HttpOnly refresh token cookie를 발급합니다."
	)
	public ResponseEntity<ApiResponse<LoginResponse>> login(@Valid @RequestBody LoginRequest request) {
		LoginResult result = authService.login(request);
		ResponseCookie refreshTokenCookie = refreshTokenCookieProvider.createCookie(result.refreshToken());

		return ResponseEntity.ok()
			.header(HttpHeaders.SET_COOKIE, refreshTokenCookie.toString())
			.body(new ApiResponse<>(true, SuccessCode.OK.getCode(), SuccessCode.OK.getMessage(), result.response()));
	}

	@PostMapping("/refresh")
	@Operation(
		summary = "Access Token 재발급",
		description = "HttpOnly refresh token cookie를 검증하고 새 access token을 발급합니다."
	)
	public ResponseEntity<ApiResponse<TokenReissueResponse>> reissueAccessToken(HttpServletRequest request) {
		String refreshToken = refreshTokenCookieProvider.resolveRefreshToken(request);
		TokenReissueResponse response = authService.reissueAccessToken(refreshToken);

		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@PostMapping("/logout")
	@Operation(
		summary = "로그아웃",
		description = "저장된 refresh token을 삭제하고 refresh token cookie를 만료시킵니다."
	)
	public ResponseEntity<ApiResponse<Void>> logout(HttpServletRequest request) {
		String refreshToken = refreshTokenCookieProvider.resolveRefreshToken(request);
		ResponseCookie expiredRefreshTokenCookie = refreshTokenCookieProvider.createExpiredCookie();

		authService.logout(refreshToken);

		return ResponseEntity.status(SuccessCode.OK.getHttpStatus())
			.header(HttpHeaders.SET_COOKIE, expiredRefreshTokenCookie.toString())
			.body(new ApiResponse<>(true, SuccessCode.OK.getCode(), SuccessCode.OK.getMessage(), null));
	}
}

