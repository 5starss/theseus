package com.theseus.api.domain.user.dto.request;

import com.theseus.api.domain.user.entity.UserStatus;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class UserStatusUpdateRequest {

	@NotNull
	private UserStatus status;
}
