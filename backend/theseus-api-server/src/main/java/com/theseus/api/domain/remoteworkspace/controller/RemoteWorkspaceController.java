package com.theseus.api.domain.remoteworkspace.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceCreateRequest;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceUpdateRequest;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceConnectionTestResponse;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceResponse;
import com.theseus.api.domain.remoteworkspace.service.RemoteWorkspaceService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "RemoteWorkspace", description = "Remote Workspace API")
@RequestMapping("/api/v1/projects/{projectId}/remote-workspaces")
public class RemoteWorkspaceController {

	private final RemoteWorkspaceService remoteWorkspaceService;

	@Operation(summary = "RemoteWorkspace create", description = "Registers an external server workspace for a project.")
	@PostMapping
	public ResponseEntity<ApiResponse<RemoteWorkspaceResponse>> createRemoteWorkspace(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@Valid @RequestBody RemoteWorkspaceCreateRequest request
	) {
		RemoteWorkspaceResponse response = remoteWorkspaceService.createRemoteWorkspace(currentUser, projectId, request);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}

	@Operation(summary = "RemoteWorkspace list", description = "Returns active remote workspaces for a project.")
	@GetMapping
	public ResponseEntity<ApiResponse<List<RemoteWorkspaceResponse>>> getRemoteWorkspaces(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId
	) {
		List<RemoteWorkspaceResponse> responses = remoteWorkspaceService.getRemoteWorkspaces(currentUser, projectId);
		return ApiResponse.onSuccess(SuccessCode.OK, responses);
	}

	@Operation(summary = "RemoteWorkspace detail", description = "Returns a single remote workspace.")
	@GetMapping("/{remoteWorkspaceId}")
	public ResponseEntity<ApiResponse<RemoteWorkspaceResponse>> getRemoteWorkspace(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long remoteWorkspaceId
	) {
		RemoteWorkspaceResponse response = remoteWorkspaceService.getRemoteWorkspace(
			currentUser,
			projectId,
			remoteWorkspaceId
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(summary = "RemoteWorkspace update", description = "Updates remote workspace connection information.")
	@PatchMapping("/{remoteWorkspaceId}")
	public ResponseEntity<ApiResponse<RemoteWorkspaceResponse>> updateRemoteWorkspace(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long remoteWorkspaceId,
		@Valid @RequestBody RemoteWorkspaceUpdateRequest request
	) {
		RemoteWorkspaceResponse response = remoteWorkspaceService.updateRemoteWorkspace(
			currentUser,
			projectId,
			remoteWorkspaceId,
			request
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(summary = "RemoteWorkspace delete", description = "Marks a remote workspace as deleted.")
	@PatchMapping("/{remoteWorkspaceId}/delete")
	public ResponseEntity<ApiResponse<RemoteWorkspaceResponse>> deleteRemoteWorkspace(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long remoteWorkspaceId
	) {
		RemoteWorkspaceResponse response = remoteWorkspaceService.deleteRemoteWorkspace(
			currentUser,
			projectId,
			remoteWorkspaceId
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(summary = "RemoteWorkspace connection test", description = "Returns a placeholder response until Core SSH Connector is integrated.")
	@PostMapping("/{remoteWorkspaceId}/test-connection")
	public ResponseEntity<ApiResponse<RemoteWorkspaceConnectionTestResponse>> testConnection(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long remoteWorkspaceId
	) {
		RemoteWorkspaceConnectionTestResponse response = remoteWorkspaceService.testConnection(
			currentUser,
			projectId,
			remoteWorkspaceId
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
