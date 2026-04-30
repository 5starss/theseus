package com.theseus.api.domain.project.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.theseus.api.common.exception.CustomException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.dto.request.ProjectMemberCreateRequest;
import com.theseus.api.domain.project.dto.response.ProjectMemberResponse;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
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
			.isInstanceOf(CustomException.class)
			.extracting(exception -> ((CustomException) exception).getErrorCode())
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
			.isInstanceOf(CustomException.class)
			.extracting(exception -> ((CustomException) exception).getErrorCode())
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
			.isInstanceOf(CustomException.class)
			.extracting(exception -> ((CustomException) exception).getErrorCode())
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
