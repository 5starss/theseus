package com.theseus.api.domain.user.service;

import com.theseus.api.common.exception.CustomException;
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

	public Page<UserResponse> getUsers(Pageable pageable) {
		return userRepository.findBySystemRoleNot(SystemRole.SUPER_ADMIN, pageable)
				.map(UserResponse::createFrom);
	}

	public UserResponse getUser(Long userId) {
		User user = getUserEntity(userId);

		return UserResponse.createFrom(user);
	}

	public UserResponse getUserByEmployeeNumber(String employeeNumber) {
		User user = userRepository.findByEmployeeNumber(employeeNumber)
				.orElseThrow(() -> new CustomException(ErrorCode.USER_NOT_FOUND));
		return UserResponse.createFrom(user);
	}

	@Transactional
	public UserResponse createUser(UserCreateRequest request) {
		validateCreateRequest(request);

		User user = request.toEntity(passwordEncoder.encode(request.getPassword()));
		User savedUser = userRepository.save(user);

		return UserResponse.createFrom(savedUser);
	}

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
				.orElseThrow(() -> new CustomException(ErrorCode.USER_NOT_FOUND));
	}

	private void validateCreateRequest(UserCreateRequest request) {
		if (userRepository.existsByEmployeeNumber(request.getEmployeeNumber())) {
			throw new CustomException(ErrorCode.DUPLICATE_EMPLOYEE_NUMBER);
		}
		if (request.getEmail() != null && userRepository.existsByEmail(request.getEmail())) {
			throw new CustomException(ErrorCode.DUPLICATE_EMAIL);
		}
	}

	private void validateEmailDuplication(Long userId, String email) {
		if (email != null && userRepository.existsByEmailAndIdNot(email, userId)) {
			throw new CustomException(ErrorCode.DUPLICATE_EMAIL);
		}
	}

	private void validateCanDeactivateUser(User user) {
		if (projectRepository.existsByProjectAdminUserAndStatus(user, ProjectStatus.ACTIVE)) {
			throw new CustomException(ErrorCode.ACTIVE_PROJECT_ADMIN_USER);
		}
	}
}
