package com.theseus.api.domain.tool.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import jakarta.persistence.EntityManager;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest
@Transactional
class ToolPlanRunRepositoryTest {

	@Autowired
	private ToolPlanRunRepository toolPlanRunRepository;

	@Autowired
	private ChatSessionRepository chatSessionRepository;

	@Autowired
	private ProjectMemberRepository projectMemberRepository;

	@Autowired
	private ProjectRepository projectRepository;

	@Autowired
	private UserRepository userRepository;

	@Autowired
	private EntityManager entityManager;

	@Test
	@DisplayName("제한 시간 초과 Run 조회는 요청 시간이 아니라 마지막 갱신 시간을 기준으로 한다")
	void findTimedOutRunsUsesUpdatedAtCutoff() {
		// Given
		ProjectFixture fixture = createProjectFixture();
		LocalDateTime oldRequestedAt = LocalDateTime.of(2026, 5, 11, 10, 0);
		ToolPlanRun recentlyUpdatedRun = createToolPlanRun(fixture, "recently-updated", oldRequestedAt);
		ToolPlanRun staleRun = createToolPlanRun(fixture, "stale-updated", oldRequestedAt);
		LocalDateTime cutoff = LocalDateTime.now().minusMinutes(1);
		LocalDateTime staleUpdatedAt = cutoff.minusMinutes(1);
		updateRunUpdatedAt(staleRun.getRunId(), staleUpdatedAt);

		// When
		List<ToolPlanRun> timedOutRuns = toolPlanRunRepository.findTimedOutRunsForUpdate(
			List.of(ToolPlanRunStatus.REQUESTED, ToolPlanRunStatus.GENERATING),
			cutoff
		);

		// Then
		assertThat(timedOutRuns)
			.extracting(ToolPlanRun::getRunId)
			.contains(staleRun.getRunId())
			.doesNotContain(recentlyUpdatedRun.getRunId());
	}

	private ToolPlanRun createToolPlanRun(ProjectFixture fixture, String runIdPrefix, LocalDateTime requestedAt) {
		return toolPlanRunRepository.save(ToolPlanRun.builder()
			.runId(runIdPrefix + "-" + UUID.randomUUID())
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.requestType(ToolPlanRunRequestType.GENERATE_PLAN)
			.mode(ToolPlanMode.PLAN)
			.status(ToolPlanRunStatus.REQUESTED)
			.requestedByProjectMember(fixture.projectMember())
			.requestedAt(requestedAt)
			.build());
	}

	private void updateRunUpdatedAt(String runId, LocalDateTime updatedAt) {
		entityManager.flush();
		entityManager.createNativeQuery("""
				update tool_plan_runs
				set updated_at = :updatedAt
				where run_id = :runId
			""")
			.setParameter("updatedAt", updatedAt)
			.setParameter("runId", runId)
			.executeUpdate();
		entityManager.flush();
		entityManager.clear();
	}

	private ProjectFixture createProjectFixture() {
		String suffix = UUID.randomUUID().toString().substring(0, 8);
		User user = userRepository.save(User.builder()
			.employeeNumber("R255" + suffix)
			.name("Run Repository User")
			.password("encoded-password")
			.build());
		Project project = projectRepository.save(Project.builder()
			.name("Run Repository Project " + suffix)
			.createdByUser(user)
			.projectAdminUser(user)
			.build());
		ProjectMember projectMember = projectMemberRepository.save(ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.ADMIN)
			.build());
		ChatSession chatSession = chatSessionRepository.save(ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Run Repository Session")
			.build());
		return new ProjectFixture(project, projectMember, chatSession);
	}

	private record ProjectFixture(Project project, ProjectMember projectMember, ChatSession chatSession) {
	}
}
