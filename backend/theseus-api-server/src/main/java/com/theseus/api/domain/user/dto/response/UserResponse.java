package com.theseus.api.domain.user.dto.response;

import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class UserResponse {

	private Long id;
	private String employeeNumber;
	private String name;
	private String email;
	private SystemRole systemRole;
	private UserStatus status;
	private boolean isSuperAdmin;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static UserResponse createFrom(User user) {
		return UserResponse.builder()
			.id(user.getId())
			.employeeNumber(user.getEmployeeNumber())
			.name(user.getName())
			.email(user.getEmail())
			.systemRole(user.getSystemRole())
			.status(user.getStatus())
			.isSuperAdmin(user.isSuperAdmin())
			.createdAt(user.getCreatedAt())
			.updatedAt(user.getUpdatedAt())
			.build();
	}
}
