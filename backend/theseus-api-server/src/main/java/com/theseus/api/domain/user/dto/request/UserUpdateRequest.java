package com.theseus.api.domain.user.dto.request;

import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.UserStatus;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class UserUpdateRequest {

	@NotBlank
	@Size(max = 100)
	private String name;

	@Email
	@Size(max = 100)
	private String email;

	@NotBlank
	@Size(max = 255)
	private String password;

	private SystemRole systemRole;

	private UserStatus status;
}
