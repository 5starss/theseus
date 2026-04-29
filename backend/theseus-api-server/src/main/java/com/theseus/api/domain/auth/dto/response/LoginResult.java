package com.theseus.api.domain.auth.dto.response;

public record LoginResult(
	LoginResponse response,
	String refreshToken
) {
}
