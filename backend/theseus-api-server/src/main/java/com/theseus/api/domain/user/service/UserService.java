package com.theseus.api.domain.user.service;

import com.theseus.api.common.exception.CustomException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.user.dto.request.UserCreateRequest;
import com.theseus.api.domain.user.dto.request.UserUpdateRequest;
import com.theseus.api.domain.user.dto.response.UserResponse;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;


@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class UserService {

	private final UserRepository userRepository;
	private final PasswordEncoder passwordEncoder;

	public List<UserResponse> getUsers() {
		return userRepository.findAll().stream()
			.map(UserResponse::createFrom)
			.toList();
	}

	public UserResponse getUser(Long userId) {
		User user = getUserEntity(userId);

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

		SystemRole systemRole = request.getSystemRole() == null ? user.getSystemRole() : request.getSystemRole();
		UserStatus status = request.getStatus() == null ? user.getStatus() : request.getStatus();

		user.update(
			request.getName(),
			request.getEmail(),
			passwordEncoder.encode(request.getPassword()),
			systemRole,
			status
		);

		return UserResponse.createFrom(user);
	}

	@Transactional
	public UserResponse deleteUser(Long userId) {
		User user = getUserEntity(userId);

		user.deactivate();

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
}
