package com.theseus.api.domain.remoteworkspace.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceConnectionConfigRequest;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceConnectionConfigResponse;
import com.theseus.api.domain.remoteworkspace.service.RemoteWorkspaceService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("/api/internal/remote-workspaces")
@RestController
public class InternalRemoteWorkspaceController {

	private final RemoteWorkspaceService remoteWorkspaceService;

	@PostMapping("/connection-config")
	public ResponseEntity<ApiResponse<RemoteWorkspaceConnectionConfigResponse>> getConnectionConfig(
		@Valid @RequestBody RemoteWorkspaceConnectionConfigRequest request
	) {
		RemoteWorkspaceConnectionConfigResponse response = remoteWorkspaceService.getConnectionConfig(request);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
