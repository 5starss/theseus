package com.theseus.api.domain.user.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.user.dto.request.UserCreateRequest;
import com.theseus.api.domain.user.dto.request.UserStatusUpdateRequest;
import com.theseus.api.domain.user.dto.request.UserUpdateRequest;
import com.theseus.api.domain.user.dto.response.UserResponse;
import com.theseus.api.domain.user.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@Tag(name = "User", description = "사용자 계정 관리 API")
@RequestMapping("/api/v1/admin/users")
@RestController
public class UserController {

	private final UserService userService;

	@GetMapping
	@Operation(summary = "사용자 목록 조회", description = "Super Admin이 등록된 사용자 계정 목록을 조회합니다.")
	public ResponseEntity<ApiResponse<Page<UserResponse>>> getUsers(
			@RequestParam(defaultValue = "0") int page,
			@RequestParam(defaultValue = "10") int size) {
		return ApiResponse.onSuccess(SuccessCode.OK, userService.getUsers(PageRequest.of(page, size)));
	}

	@GetMapping("/{userId}")
	@Operation(summary = "사용자 단건 조회", description = "Super Admin이 사용자 ID로 등록된 사용자 계정 상세 정보를 조회합니다.")
	public ResponseEntity<ApiResponse<UserResponse>> getUser(@PathVariable Long userId) {
		return ApiResponse.onSuccess(SuccessCode.OK, userService.getUser(userId));
	}

	@PostMapping
	@Operation(summary = "사용자 계정 발급", description = "Super Admin이 새 사용자 계정을 발급합니다. 일반 회원가입 API가 아니며, 입력받은 비밀번호는 BCrypt로 해싱되어 저장됩니다.")
	public ResponseEntity<ApiResponse<UserResponse>> createUser(@Valid @RequestBody UserCreateRequest request) {
		return ApiResponse.onSuccess(SuccessCode.CREATED, userService.createUser(request));
	}

	@PatchMapping("/{userId}")
	@Operation(summary = "사용자 기본 정보 수정", description = "Super Admin이 사용자 이름, 이메일, 시스템 권한을 수정합니다.")
	public ResponseEntity<ApiResponse<UserResponse>> updateUser(
			@PathVariable Long userId,
			@Valid @RequestBody UserUpdateRequest request) {
		return ApiResponse.onSuccess(SuccessCode.OK, userService.updateUser(userId, request));
	}

	@PatchMapping("/{userId}/status")
	@Operation(summary = "사용자 상태 변경", description = "Super Admin이 사용자 상태를 변경합니다. 활성 프로젝트의 담당자(PM)는 INACTIVE로 변경할 수 없습니다.")
	public ResponseEntity<ApiResponse<UserResponse>> updateUserStatus(
			@PathVariable Long userId,
			@Valid @RequestBody UserStatusUpdateRequest request) {
		return ApiResponse.onSuccess(SuccessCode.OK, userService.updateUserStatus(userId, request));
	}
}
