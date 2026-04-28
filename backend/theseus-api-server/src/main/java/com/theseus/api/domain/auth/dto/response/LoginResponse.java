package com.theseus.api.domain.auth.dto.response;

import com.theseus.api.domain.user.entity.SystemRole;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class LoginResponse {

	private String tokenType;
	private String accessToken;
	private Long userId;
	private String name;
	private SystemRole systemRole;
}
