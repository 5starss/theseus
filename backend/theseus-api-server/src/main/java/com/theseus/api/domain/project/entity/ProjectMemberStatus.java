package com.theseus.api.domain.project.entity;

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
			.filter(status -> status.text.equals(text))
			.findFirst()
			.orElseThrow(() -> new IllegalArgumentException("지원하지 않는 프로젝트 멤버 상태입니다."));
	}
}
