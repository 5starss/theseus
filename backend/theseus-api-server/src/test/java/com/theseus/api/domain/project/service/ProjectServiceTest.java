package com.theseus.api.domain.project.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.dto.request.ProjectCreateRequest;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectAccessLevelPolicy;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.SystemRole;
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
class ProjectServiceTest {

	@Autowired
	private ProjectService projectService;

	@Autowired
	private ProjectRepository projectRepository;

	@Autowired
	private ProjectMemberRepository projectMemberRepository;

	@Autowired
	private UserRepository userRepository;

	@Test
	@DisplayName("프로젝트 생성 시 PM은 ADMIN 권한과 accessLevel 100으로 등록된다")
	void createProjectRegistersAdminMemberWithAdminAccessLevel() {
		// Given
		User superAdmin = createUser("A287001", "Super Admin", SystemRole.SUPER_ADMIN);
		User projectAdminUser = createUser("A287002", "Project Admin", SystemRole.USER);
		ProjectCreateRequest request = createProjectCreateRequest(projectAdminUser);

		// When
		projectService.createProject(createAuthenticatedUser(superAdmin), request);

		// Then
		Project project = projectRepository.findAll().stream()
			.filter(savedProject -> "Admin Access Project".equals(savedProject.getName()))
			.findFirst()
			.orElseThrow();
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, projectAdminUser)
			.orElseThrow();
		assertThat(project.getProjectAdminUser()).isEqualTo(projectAdminUser);
		assertThat(projectMember.getProjectRole()).isEqualTo(ProjectRole.ADMIN);
		assertThat(projectMember.getAccessLevel()).isEqualTo(ProjectAccessLevelPolicy.ADMIN_ACCESS_LEVEL);
		assertThat(projectMember.getCanCreateTool()).isTrue();
		assertThat(projectMember.getCanUseTool()).isTrue();
		assertThat(projectMember.getCanUpdateTool()).isTrue();
		assertThat(projectMember.getCanDeleteTool()).isTrue();
	}

	private ProjectCreateRequest createProjectCreateRequest(User projectAdminUser) {
		ProjectCreateRequest request = new ProjectCreateRequest();
		ReflectionTestUtils.setField(request, "name", "Admin Access Project");
		ReflectionTestUtils.setField(request, "description", "Admin access policy project");
		ReflectionTestUtils.setField(request, "adminEmployeeNumber", projectAdminUser.getEmployeeNumber());
		ReflectionTestUtils.setField(request, "adminName", projectAdminUser.getName());

		return request;
	}

	private User createUser(String employeeNumber, String name, SystemRole systemRole) {
		return userRepository.save(User.builder()
			.employeeNumber(employeeNumber)
			.name(name)
			.password("encoded-password")
			.systemRole(systemRole)
			.status(UserStatus.ACTIVE)
			.build());
	}

	private AuthenticatedUser createAuthenticatedUser(User user) {
		return new AuthenticatedUser(
			user.getId(),
			user.getEmployeeNumber(),
			user.getName(),
			user.getSystemRole()
		);
	}
}
