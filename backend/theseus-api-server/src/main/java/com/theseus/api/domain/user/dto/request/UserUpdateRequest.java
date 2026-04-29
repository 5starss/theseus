package com.theseus.api.domain.user.dto.request;

import com.theseus.api.domain.user.entity.SystemRole;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class UserUpdateRequest {

	@Size(max = 100)
	private String name;

	@Email
	@Size(max = 100)
	private String email;

	private SystemRole systemRole;
}
