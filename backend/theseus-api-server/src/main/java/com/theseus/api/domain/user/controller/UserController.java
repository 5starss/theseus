package com.theseus.api.domain.user.controller;

import com.theseus.api.domain.user.dto.request.UserCreateRequest;
import com.theseus.api.domain.user.dto.request.UserUpdateRequest;
import com.theseus.api.domain.user.dto.response.UserResponse;
import com.theseus.api.domain.user.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@Tag(name = "User", description = "사용자 계정 관리 API")
@RequestMapping("/users")
@RestController
public class UserController {

	private final UserService userService;

	@GetMapping
	@Operation(
		summary = "사용자 목록 조회",
		description = "등록된 사용자 계정 목록을 조회합니다. 사용자 계정은 일반 회원가입이 아니라 Super Admin이 발급하는 대상입니다."
	)
	public ResponseEntity<List<UserResponse>> getUsers() {
		return ResponseEntity.ok(userService.getUsers());
	}

	@GetMapping("/{userId}")
	@Operation(
		summary = "사용자 단건 조회",
		description = "사용자 ID로 등록된 사용자 계정 상세 정보를 조회합니다."
	)
	public ResponseEntity<UserResponse> getUser(@PathVariable Long userId) {
		return ResponseEntity.ok(userService.getUser(userId));
	}

	@PostMapping
	@Operation(
		summary = "사용자 계정 발급",
		description = "Super Admin이 새 사용자 계정을 발급합니다. 일반 회원가입 API가 아니며, 입력받은 비밀번호는 BCrypt로 해싱되어 저장됩니다."
	)
	public ResponseEntity<UserResponse> createUser(@Valid @RequestBody UserCreateRequest request) {
		return ResponseEntity.status(HttpStatus.CREATED)
			.body(userService.createUser(request));
	}

	@PostMapping("/{userId}/update")
	@Operation(
		summary = "사용자 계정 수정",
		description = "사용자 이름, 이메일, 비밀번호, 시스템 권한, 계정 상태를 수정합니다. 비밀번호를 수정하면 BCrypt로 다시 해싱되어 저장됩니다."
	)
	public ResponseEntity<UserResponse> updateUser(
		@PathVariable Long userId,
		@Valid @RequestBody UserUpdateRequest request
	) {
		return ResponseEntity.ok(userService.updateUser(userId, request));
	}

	@PostMapping("/{userId}/delete")
	@Operation(
		summary = "사용자 계정 비활성화",
		description = "사용자 계정을 물리 삭제하지 않고 INACTIVE 상태로 변경합니다."
	)
	public ResponseEntity<UserResponse> deleteUser(@PathVariable Long userId) {
		return ResponseEntity.ok(userService.deleteUser(userId));
	}
}
