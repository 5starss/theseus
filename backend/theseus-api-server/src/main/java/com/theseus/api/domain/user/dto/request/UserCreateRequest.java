package com.theseus.api.domain.user.dto.request;

import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class UserCreateRequest {

	@NotBlank
	@Size(max = 50)
	private String employeeNumber;

	@NotBlank
	@Size(max = 100)
	private String name;

	@Email
	@Size(max = 100)
	private String email;

	@NotBlank
	@Size(max = 255)
	private String password;

	private SystemRole systemRole = SystemRole.USER;

	private UserStatus status = UserStatus.ACTIVE;

	public User toEntity(String encodedPassword) {
		return User.builder()
			.employeeNumber(employeeNumber)
			.name(name)
			.email(email)
			.password(encodedPassword)
			.systemRole(systemRole)
			.status(status)
			.build();
	}
}
