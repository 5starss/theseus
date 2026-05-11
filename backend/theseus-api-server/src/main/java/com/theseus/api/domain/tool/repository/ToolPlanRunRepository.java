package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import jakarta.persistence.LockModeType;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ToolPlanRunRepository extends JpaRepository<ToolPlanRun, Long> {

	Optional<ToolPlanRun> findByRunId(String runId);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select toolPlanRun
		from ToolPlanRun toolPlanRun
		where toolPlanRun.runId = :runId
	""")
	Optional<ToolPlanRun> findByRunIdForUpdate(@Param("runId") String runId);

	Optional<ToolPlanRun> findByRunIdAndProjectAndChatSession(String runId, Project project, ChatSession chatSession);

	List<ToolPlanRun> findByProjectAndChatSessionAndStatusOrderByRequestedAtDesc(
		Project project,
		ChatSession chatSession,
		ToolPlanRunStatus status
	);

	boolean existsByRunId(String runId);
}
