package com.theseus.api.domain.user.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.project.entity.ProjectStatus;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.dto.request.UserCreateRequest;
import com.theseus.api.domain.user.dto.request.UserStatusUpdateRequest;
import com.theseus.api.domain.user.dto.request.UserUpdateRequest;
import com.theseus.api.domain.user.dto.response.UserResponse;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class UserService {

	private final UserRepository userRepository;
	private final ProjectRepository projectRepository;
	private final PasswordEncoder passwordEncoder;

	/**
	 * Super Admin을 제외한 사용자 목록을 페이지 단위로 조회합니다.
	 */
	public Page<UserResponse> getUsers(Pageable pageable) {
		return userRepository.findBySystemRoleNot(SystemRole.SUPER_ADMIN, pageable)
				.map(UserResponse::createFrom);
	}

	/**
	 * 사용자 ID로 사용자 상세 정보를 조회합니다.
	 */
	public UserResponse getUser(Long userId) {
		User user = getUserEntity(userId);

		return UserResponse.createFrom(user);
	}

	/**
	 * 사번으로 사용자 정보를 조회합니다.
	 */
	public UserResponse getUserByEmployeeNumber(String employeeNumber) {
		User user = userRepository.findByEmployeeNumber(employeeNumber)
				.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
		return UserResponse.createFrom(user);
	}

	/**
	 * Super Admin이 새 사용자 계정을 발급합니다.
	 */
	@Transactional
	public UserResponse createUser(UserCreateRequest request) {
		validateCreateRequest(request);

		User user = request.toEntity(passwordEncoder.encode(request.getPassword()));
		User savedUser = userRepository.save(user);

		return UserResponse.createFrom(savedUser);
	}

	/**
	 * 사용자 기본 정보와 시스템 권한을 수정합니다.
	 */
	@Transactional
	public UserResponse updateUser(Long userId, UserUpdateRequest request) {
		User user = getUserEntity(userId);
		validateEmailDuplication(userId, request.getEmail());

		user.update(
				request.getName(),
				request.getEmail(),
				null,
				request.getSystemRole());

		return UserResponse.createFrom(user);
	}

	/**
	 * 사용자 활성 상태를 변경하고 비활성화 가능 여부를 검증합니다.
	 */
	@Transactional
	public UserResponse updateUserStatus(Long userId, UserStatusUpdateRequest request) {
		User user = getUserEntity(userId);

		if (UserStatus.INACTIVE.equals(request.getStatus())) {
			validateCanDeactivateUser(user);
		}

		user.updateStatus(request.getStatus());

		return UserResponse.createFrom(user);
	}

	private User getUserEntity(Long userId) {
		return userRepository.findById(userId)
				.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
	}

	private void validateCreateRequest(UserCreateRequest request) {
		if (userRepository.existsByEmployeeNumber(request.getEmployeeNumber())) {
			throw BusinessException.of(ErrorCode.DUPLICATE_EMPLOYEE_NUMBER);
		}
		if (request.getEmail() != null && userRepository.existsByEmail(request.getEmail())) {
			throw BusinessException.of(ErrorCode.DUPLICATE_EMAIL);
		}
	}

	private void validateEmailDuplication(Long userId, String email) {
		if (email != null && userRepository.existsByEmailAndIdNot(email, userId)) {
			throw BusinessException.of(ErrorCode.DUPLICATE_EMAIL);
		}
	}

	private void validateCanDeactivateUser(User user) {
		if (projectRepository.existsByProjectAdminUserAndStatus(user, ProjectStatus.ACTIVE)) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_ADMIN_USER);
		}
	}
}
