package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import jakarta.persistence.LockModeType;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ToolPlanRepository extends JpaRepository<ToolPlan, Long> {

	List<ToolPlan> findByPlanGroupOrderByPlanVersionDesc(ToolPlanGroup planGroup);

	List<ToolPlan> findByPlanGroupAndStatusOrderByPlanVersionDesc(
		ToolPlanGroup planGroup,
		ToolPlanStatus status
	);

	Optional<ToolPlan> findByPlanGroupAndPlanVersion(ToolPlanGroup planGroup, Long planVersion);

	Optional<ToolPlan> findByIdAndProjectAndChatSession(Long id, Project project, ChatSession chatSession);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select toolPlan
		from ToolPlan toolPlan
		where toolPlan.id = :id
			and toolPlan.project = :project
			and toolPlan.chatSession = :chatSession
	""")
	Optional<ToolPlan> findByIdAndProjectAndChatSessionForUpdate(
		@Param("id") Long id,
		@Param("project") Project project,
		@Param("chatSession") ChatSession chatSession
	);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select toolPlan
		from ToolPlan toolPlan
		where toolPlan.id = :id
			and toolPlan.project = :project
	""")
	Optional<ToolPlan> findByIdAndProjectForUpdate(
		@Param("id") Long id,
		@Param("project") Project project
	);

	boolean existsByPlanGroupAndPlanVersion(ToolPlanGroup planGroup, Long planVersion);
}
