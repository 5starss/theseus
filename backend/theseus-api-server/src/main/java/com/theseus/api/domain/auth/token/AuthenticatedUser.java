package com.theseus.api.domain.auth.token;

import com.theseus.api.domain.user.entity.SystemRole;

public record AuthenticatedUser(
	Long userId,
	String employeeNumber,
	String name,
	SystemRole systemRole
) {
}
