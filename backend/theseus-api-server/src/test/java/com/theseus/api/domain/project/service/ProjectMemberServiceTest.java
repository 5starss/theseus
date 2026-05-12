package com.theseus.api.domain.project.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.dto.request.ProjectMemberCreateRequest;
import com.theseus.api.domain.project.dto.request.ProjectMemberUpdateRequest;
import com.theseus.api.domain.project.dto.response.ProjectMemberResponse;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectAccessLevelPolicy;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest
@Transactional
class ProjectMemberServiceTest {

	@Autowired
	private ProjectMemberService projectMemberService;

	@Autowired
	private ProjectMemberRepository projectMemberRepository;

	@Autowired
	private ProjectRepository projectRepository;

	@Autowired
	private UserRepository userRepository;

	@Test
	@DisplayName("Project ADMIN can register an active user by employee number")
	void createProjectMemberWithEmployeeNumber() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155001");
		User targetUser = createUser("A155002", UserStatus.ACTIVE);
		ProjectMemberCreateRequest request = createMemberCreateRequest(targetUser.getEmployeeNumber(), ProjectRole.MANAGER);

		// When
		ProjectMemberResponse response = projectMemberService.createProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			request
		);

		// Then
		ProjectMember savedProjectMember = projectMemberRepository.findByProjectAndUser(
			fixture.project(),
			targetUser
		).orElseThrow();
		assertThat(response.getUserId()).isEqualTo(targetUser.getId());
		assertThat(response.getEmployeeNumber()).isEqualTo(targetUser.getEmployeeNumber());
		assertThat(response.getProjectRole()).isEqualTo(ProjectRole.MANAGER);
		assertThat(savedProjectMember.getUser().getId()).isEqualTo(targetUser.getId());
	}

	@Test
	@DisplayName("ADMIN 프로젝트 멤버 등록 시 accessLevel은 100으로 보정되고 Tool 권한은 모두 허용된다")
	void createAdminProjectMemberNormalizesAccessLevel() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155041");
		User targetUser = createUser("A155042", UserStatus.ACTIVE);
		ProjectMemberCreateRequest request = createMemberCreateRequest(targetUser.getEmployeeNumber(), ProjectRole.ADMIN);
		ReflectionTestUtils.setField(request, "accessLevel", 50);

		// When
		projectMemberService.createProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			request
		);

		// Then
		ProjectMember savedProjectMember = projectMemberRepository.findByProjectAndUser(
			fixture.project(),
			targetUser
		).orElseThrow();
		assertThat(savedProjectMember.getProjectRole()).isEqualTo(ProjectRole.ADMIN);
		assertThat(savedProjectMember.getAccessLevel()).isEqualTo(ProjectAccessLevelPolicy.ADMIN_ACCESS_LEVEL);
		assertThat(savedProjectMember.getCanCreateTool()).isTrue();
		assertThat(savedProjectMember.getCanUseTool()).isTrue();
		assertThat(savedProjectMember.getCanUpdateTool()).isTrue();
		assertThat(savedProjectMember.getCanDeleteTool()).isTrue();
	}

	@Test
	@DisplayName("일반 프로젝트 멤버 등록 시 accessLevel 100은 거부된다")
	void createProjectMemberFailsWhenMemberAccessLevelIsAdminOnly() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155051");
		User targetUser = createUser("A155052", UserStatus.ACTIVE);
		ProjectMemberCreateRequest request = createMemberCreateRequest(targetUser.getEmployeeNumber(), ProjectRole.MEMBER);
		ReflectionTestUtils.setField(request, "accessLevel", ProjectAccessLevelPolicy.ADMIN_ACCESS_LEVEL);

		// When & Then
		assertThatThrownBy(() -> projectMemberService.createProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			request
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.INVALID_PROJECT_MEMBER_ACCESS_LEVEL);
	}

	@Test
	@DisplayName("기존 멤버를 ADMIN으로 변경하면 accessLevel은 100으로 보정된다")
	void updateProjectMemberToAdminNormalizesAccessLevel() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155061");
		User targetUser = createUser("A155062", UserStatus.ACTIVE);
		ProjectMember targetProjectMember = createProjectMember(fixture.project(), targetUser, ProjectRole.MEMBER);
		ProjectMemberUpdateRequest request = createMemberUpdateRequest(ProjectRole.ADMIN, 3);

		// When
		projectMemberService.updateProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			targetProjectMember.getId(),
			request
		);

		// Then
		assertThat(targetProjectMember.getProjectRole()).isEqualTo(ProjectRole.ADMIN);
		assertThat(targetProjectMember.getAccessLevel()).isEqualTo(ProjectAccessLevelPolicy.ADMIN_ACCESS_LEVEL);
		assertThat(targetProjectMember.getCanCreateTool()).isTrue();
		assertThat(targetProjectMember.getCanUseTool()).isTrue();
		assertThat(targetProjectMember.getCanUpdateTool()).isTrue();
		assertThat(targetProjectMember.getCanDeleteTool()).isTrue();
	}

	@Test
	@DisplayName("ADMIN에서 제외된 멤버는 accessLevel이 1로 초기화된다")
	void updateProjectMemberFromAdminToMemberResetsAccessLevel() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155071");
		User targetUser = createUser("A155072", UserStatus.ACTIVE);
		ProjectMember targetProjectMember = createProjectMember(fixture.project(), targetUser, ProjectRole.ADMIN);
		ProjectMemberUpdateRequest request = createMemberUpdateRequest(ProjectRole.MEMBER, 50);

		// When
		projectMemberService.updateProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			targetProjectMember.getId(),
			request
		);

		// Then
		assertThat(targetProjectMember.getProjectRole()).isEqualTo(ProjectRole.MEMBER);
		assertThat(targetProjectMember.getAccessLevel()).isEqualTo(ProjectAccessLevelPolicy.DEFAULT_MEMBER_ACCESS_LEVEL);
	}

	@Test
	@DisplayName("일반 프로젝트 멤버 수정 시 accessLevel 100은 거부된다")
	void updateProjectMemberFailsWhenMemberAccessLevelIsAdminOnly() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155081");
		User targetUser = createUser("A155082", UserStatus.ACTIVE);
		ProjectMember targetProjectMember = createProjectMember(fixture.project(), targetUser, ProjectRole.MEMBER);
		ProjectMemberUpdateRequest request = createMemberUpdateRequest(ProjectRole.MEMBER, ProjectAccessLevelPolicy.ADMIN_ACCESS_LEVEL);

		// When & Then
		assertThatThrownBy(() -> projectMemberService.updateProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			targetProjectMember.getId(),
			request
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.INVALID_PROJECT_MEMBER_ACCESS_LEVEL);
	}

	@Test
	@DisplayName("Project member registration fails when employee number does not exist")
	void createProjectMemberFailsWhenEmployeeNumberDoesNotExist() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155011");
		ProjectMemberCreateRequest request = createMemberCreateRequest("A155012", ProjectRole.MEMBER);

		// When & Then
		assertThatThrownBy(() -> projectMemberService.createProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			request
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.USER_NOT_FOUND);
	}

	@Test
	@DisplayName("Project member registration fails when user is inactive")
	void createProjectMemberFailsWhenUserIsInactive() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155021");
		User inactiveUser = createUser("A155022", UserStatus.INACTIVE);
		ProjectMemberCreateRequest request = createMemberCreateRequest(inactiveUser.getEmployeeNumber(), ProjectRole.MEMBER);

		// When & Then
		assertThatThrownBy(() -> projectMemberService.createProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			request
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.PROJECT_MEMBER_ACTIVE_USER_REQUIRED);
	}

	@Test
	@DisplayName("Project member registration fails when user is already registered")
	void createProjectMemberFailsWhenAlreadyRegistered() {
		// Given
		ProjectFixture fixture = createProjectFixture("A155031");
		User targetUser = createUser("A155032", UserStatus.ACTIVE);
		createProjectMember(fixture.project(), targetUser, ProjectRole.MEMBER);
		ProjectMemberCreateRequest request = createMemberCreateRequest(targetUser.getEmployeeNumber(), ProjectRole.MEMBER);

		// When & Then
		assertThatThrownBy(() -> projectMemberService.createProjectMember(
			createAuthenticatedUser(fixture.adminUser()),
			fixture.project().getId(),
			request
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.DUPLICATE_PROJECT_MEMBER);
	}

	private ProjectFixture createProjectFixture(String employeeNumber) {
		User adminUser = createUser(employeeNumber, UserStatus.ACTIVE);
		Project project = projectRepository.save(Project.builder()
			.name("Project Member Project " + employeeNumber)
			.createdByUser(adminUser)
			.projectAdminUser(adminUser)
			.build());
		ProjectMember adminProjectMember = createProjectMember(project, adminUser, ProjectRole.ADMIN);

		return new ProjectFixture(adminUser, project, adminProjectMember);
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

	private User createUser(String employeeNumber, UserStatus status) {
		return userRepository.save(User.builder()
			.employeeNumber(employeeNumber)
			.name("Project Member User " + employeeNumber)
			.password("encoded-password")
			.status(status)
			.build());
	}

	private ProjectMemberCreateRequest createMemberCreateRequest(
		String employeeNumber,
		ProjectRole projectRole
	) {
		ProjectMemberCreateRequest request = new ProjectMemberCreateRequest();
		ReflectionTestUtils.setField(request, "employeeNumber", employeeNumber);
		ReflectionTestUtils.setField(request, "projectRole", projectRole);

		return request;
	}

	private ProjectMemberUpdateRequest createMemberUpdateRequest(ProjectRole projectRole, Integer accessLevel) {
		ProjectMemberUpdateRequest request = new ProjectMemberUpdateRequest();
		ReflectionTestUtils.setField(request, "projectRole", projectRole);
		ReflectionTestUtils.setField(request, "accessLevel", accessLevel);
		ReflectionTestUtils.setField(request, "status", ProjectMemberStatus.IN_PROGRESS);

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
