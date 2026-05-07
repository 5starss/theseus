package com.theseus.api.domain.auth.dto.response;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TokenReissueResponse {

	private String tokenType;
	private String accessToken;

	@JsonIgnore
	private String refreshToken;
}
