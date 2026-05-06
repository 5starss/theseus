package com.theseus.api.domain.project.entity;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import java.util.Arrays;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum ProjectMemberStatus {
	IN_PROGRESS("진행중"),
	COMPLETED("완료");

	private final String text;

	public static ProjectMemberStatus createFrom(String text) {
		return Arrays.stream(values())
			.filter(status -> status.name().equals(text) || status.text.equals(text))
			.findFirst()
			.orElseThrow(() -> BusinessException.of(ErrorCode.INVALID_PROJECT_MEMBER_STATUS));
	}
}
