package com.theseus.api.domain.auth.controller;

import com.theseus.api.domain.auth.dto.request.LoginRequest;
import com.theseus.api.domain.auth.dto.response.LoginResponse;
import com.theseus.api.domain.auth.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
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

	@PostMapping("/login")
	@Operation(
		summary = "로그인",
		description = "사번 또는 이메일과 비밀번호를 검증하고, 이후 API 인증에 사용할 JWT access token을 발급합니다."
	)
	public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
		return ResponseEntity.ok(authService.login(request));
	}
}
