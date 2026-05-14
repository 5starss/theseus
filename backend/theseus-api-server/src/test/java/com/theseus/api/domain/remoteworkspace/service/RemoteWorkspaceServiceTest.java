package com.theseus.api.domain.remoteworkspace.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceCreateRequest;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceUpdateRequest;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceConnectionTestResponse;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceResponse;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspaceStatus;
import com.theseus.api.domain.remoteworkspace.repository.RemoteWorkspaceRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest
@Transactional
class RemoteWorkspaceServiceTest {

	@Autowired
	private RemoteWorkspaceService remoteWorkspaceService;

	@Autowired
	private RemoteWorkspaceRepository remoteWorkspaceRepository;

	@Autowired
	private ProjectRepository projectRepository;

	@Autowired
	private ProjectMemberRepository projectMemberRepository;

	@Autowired
	private UserRepository userRepository;

	@Test
	@DisplayName("프로젝트 ADMIN은 RemoteWorkspace를 등록할 수 있다")
	void createRemoteWorkspaceByAdmin() {
		// Given
		ProjectFixture fixture = createProjectFixture("RW302001");
		RemoteWorkspaceCreateRequest request = createCreateRequest("alpha-server");

		// When
		RemoteWorkspaceResponse response = remoteWorkspaceService.createRemoteWorkspace(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			request
		);

		// Then
		RemoteWorkspace savedRemoteWorkspace = remoteWorkspaceRepository.findById(response.getRemoteWorkspaceId())
			.orElseThrow();
		assertThat(response.getProjectId()).isEqualTo(fixture.project().getId());
		assertThat(response.getName()).isEqualTo("alpha-server");
		assertThat(response.getAllowWriteExecution()).isFalse();
		assertThat(savedRemoteWorkspace.getPassword()).isEqualTo("password");
		assertThat(savedRemoteWorkspace.isAllowWriteExecution()).isFalse();
		assertThat(savedRemoteWorkspace.getStatus()).isEqualTo(RemoteWorkspaceStatus.ACTIVE);
	}

	@Test
	@DisplayName("일반 프로젝트 멤버는 RemoteWorkspace를 등록할 수 없다")
	void createRemoteWorkspaceFailsWhenNotAdmin() {
		// Given
		ProjectFixture fixture = createProjectFixture("RW302011");
		User memberUser = createUser("RW302012");
		createProjectMember(fixture.project(), memberUser, ProjectRole.MEMBER);
		RemoteWorkspaceCreateRequest request = createCreateRequest("member-server");

		// When & Then
		assertThatThrownBy(() -> remoteWorkspaceService.createRemoteWorkspace(
			createAuthenticatedUser(memberUser),
			fixture.project().getId(),
			request
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.REMOTE_WORKSPACE_ADMIN_PERMISSION_REQUIRED);
	}

	@Test
	@DisplayName("프로젝트 멤버는 삭제되지 않은 RemoteWorkspace 목록을 조회할 수 있다")
	void getRemoteWorkspaces() {
		// Given
		ProjectFixture fixture = createProjectFixture("RW302021");
		RemoteWorkspace activeRemoteWorkspace = createRemoteWorkspace(fixture, "active-server");
		RemoteWorkspace deletedRemoteWorkspace = createRemoteWorkspace(fixture, "deleted-server");
		deletedRemoteWorkspace.delete();

		// When
		List<RemoteWorkspaceResponse> responses = remoteWorkspaceService.getRemoteWorkspaces(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId()
		);

		// Then
		assertThat(responses)
			.extracting(RemoteWorkspaceResponse::getRemoteWorkspaceId)
			.containsExactly(activeRemoteWorkspace.getId());
	}

	@Test
	@DisplayName("프로젝트 ADMIN은 RemoteWorkspace 접속 정보를 수정할 수 있다")
	void updateRemoteWorkspace() {
		// Given
		ProjectFixture fixture = createProjectFixture("RW302031");
		RemoteWorkspace remoteWorkspace = createRemoteWorkspace(fixture, "before-server");
		RemoteWorkspaceUpdateRequest request = createUpdateRequest("after-server", 2222);

		// When
		RemoteWorkspaceResponse response = remoteWorkspaceService.updateRemoteWorkspace(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			remoteWorkspace.getId(),
			request
		);

		// Then
		assertThat(response.getName()).isEqualTo("after-server");
		assertThat(response.getPort()).isEqualTo(2222);
		assertThat(response.getAllowWriteExecution()).isTrue();
		assertThat(remoteWorkspace.getName()).isEqualTo("after-server");
		assertThat(remoteWorkspace.getPort()).isEqualTo(2222);
		assertThat(remoteWorkspace.isAllowWriteExecution()).isTrue();
	}

	@Test
	@DisplayName("프로젝트 ADMIN은 RemoteWorkspace를 삭제 상태로 전환할 수 있다")
	void deleteRemoteWorkspace() {
		// Given
		ProjectFixture fixture = createProjectFixture("RW302041");
		RemoteWorkspace remoteWorkspace = createRemoteWorkspace(fixture, "delete-server");

		// When
		RemoteWorkspaceResponse response = remoteWorkspaceService.deleteRemoteWorkspace(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			remoteWorkspace.getId()
		);

		// Then
		assertThat(response.getStatus()).isEqualTo(RemoteWorkspaceStatus.DELETED);
		assertThat(remoteWorkspace.isDeleted()).isTrue();
		assertThat(remoteWorkspaceRepository.findByIdAndProjectAndStatusNot(
			remoteWorkspace.getId(),
			fixture.project(),
			RemoteWorkspaceStatus.DELETED
		)).isEmpty();
	}

	@Test
	@DisplayName("연결 테스트 API는 Core SSH Connector 연동 전까지 대기 응답을 반환한다")
	void testConnectionReturnsUnavailableResponse() {
		// Given
		ProjectFixture fixture = createProjectFixture("RW302051");
		RemoteWorkspace remoteWorkspace = createRemoteWorkspace(fixture, "test-server");

		// When
		RemoteWorkspaceConnectionTestResponse response = remoteWorkspaceService.testConnection(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			remoteWorkspace.getId()
		);

		// Then
		assertThat(response.getRemoteWorkspaceId()).isEqualTo(remoteWorkspace.getId());
		assertThat(response.getAvailable()).isFalse();
		assertThat(response.getMessage()).isEqualTo(
			"Remote Workspace connection test is not enabled until secure secret resolution is ready."
		);
	}

	private ProjectFixture createProjectFixture(String employeeNumber) {
		User adminUser = createUser(employeeNumber);
		Project project = projectRepository.save(Project.builder()
			.name("Remote Workspace Project " + employeeNumber)
			.createdByUser(adminUser)
			.projectAdminUser(adminUser)
			.build());
		ProjectMember adminProjectMember = createProjectMember(project, adminUser, ProjectRole.ADMIN);

		return new ProjectFixture(adminUser, project, adminProjectMember);
	}

	private RemoteWorkspace createRemoteWorkspace(ProjectFixture fixture, String name) {
		return remoteWorkspaceRepository.save(RemoteWorkspace.builder()
			.project(fixture.project())
			.createdByProjectMember(fixture.adminProjectMember())
			.name(name)
			.host("127.0.0.1")
			.port(22)
			.username("deploy")
			.password("password")
			.basePath("/srv/app")
			.build());
	}

	private ProjectMember createProjectMember(Project project, User user, ProjectRole projectRole) {
		return projectMemberRepository.save(ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(projectRole)
			.canCreateTool(true)
			.canUseTool(true)
			.canUpdateTool(true)
			.canDeleteTool(true)
			.build());
	}

	private User createUser(String employeeNumber) {
		return userRepository.save(User.builder()
			.employeeNumber(employeeNumber)
			.name("Remote Workspace User " + employeeNumber)
			.password("encoded-password")
			.status(UserStatus.ACTIVE)
			.build());
	}

	private RemoteWorkspaceCreateRequest createCreateRequest(String name) {
		RemoteWorkspaceCreateRequest request = new RemoteWorkspaceCreateRequest();
		ReflectionTestUtils.setField(request, "name", name);
		ReflectionTestUtils.setField(request, "host", "127.0.0.1");
		ReflectionTestUtils.setField(request, "port", 22);
		ReflectionTestUtils.setField(request, "username", "deploy");
		ReflectionTestUtils.setField(request, "password", "password");
		ReflectionTestUtils.setField(request, "privateKeyPath", null);
		ReflectionTestUtils.setField(request, "basePath", "/srv/app");
		ReflectionTestUtils.setField(request, "allowWriteExecution", false);

		return request;
	}

	private RemoteWorkspaceUpdateRequest createUpdateRequest(String name, Integer port) {
		RemoteWorkspaceUpdateRequest request = new RemoteWorkspaceUpdateRequest();
		ReflectionTestUtils.setField(request, "name", name);
		ReflectionTestUtils.setField(request, "port", port);
		ReflectionTestUtils.setField(request, "allowWriteExecution", true);

		return request;
	}

	private AuthenticatedUser createAuthenticatedUser(User user) {
		return new AuthenticatedUser(
			user.getId(),
			user.getEmployeeNumber(),
			user.getName(),
			user.getSystemRole()
		);
	}

	private record ProjectFixture(
		User adminUser,
		Project project,
		ProjectMember adminProjectMember
	) {
	}
}
