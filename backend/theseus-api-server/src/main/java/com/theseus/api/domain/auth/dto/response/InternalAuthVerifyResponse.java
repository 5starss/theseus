package com.theseus.api.domain.auth.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class InternalAuthVerifyResponse {

	@JsonProperty("user_id")
	private String userId;

	@JsonProperty("project_id")
	private String projectId;

	@JsonProperty("permission_level")
	private Integer permissionLevel;
}
