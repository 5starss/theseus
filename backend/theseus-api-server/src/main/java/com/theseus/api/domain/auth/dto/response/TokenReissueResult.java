package com.theseus.api.domain.auth.dto.response;

public record TokenReissueResult(
	TokenReissueResponse response,
	String refreshToken
) {
}
