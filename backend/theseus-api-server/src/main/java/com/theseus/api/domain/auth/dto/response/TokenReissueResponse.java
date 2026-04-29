package com.theseus.api.domain.auth.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TokenReissueResponse {

	private String tokenType;
	private String accessToken;
}
