package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ToolPlanRepository extends JpaRepository<ToolPlan, Long> {

	List<ToolPlan> findByPlanGroupOrderByPlanVersionDesc(ToolPlanGroup planGroup);

	List<ToolPlan> findByPlanGroupAndStatusOrderByPlanVersionDesc(
		ToolPlanGroup planGroup,
		ToolPlanStatus status
	);

	Optional<ToolPlan> findByPlanGroupAndPlanVersion(ToolPlanGroup planGroup, Long planVersion);

	Optional<ToolPlan> findByIdAndProjectAndChatSession(Long id, Project project, ChatSession chatSession);

	boolean existsByPlanGroupAndPlanVersion(ToolPlanGroup planGroup, Long planVersion);
}
