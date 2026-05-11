package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ToolPlanGroupRepository extends JpaRepository<ToolPlanGroup, Long> {

	List<ToolPlanGroup> findByProjectAndChatSessionOrderByUpdatedAtDesc(Project project, ChatSession chatSession);

	List<ToolPlanGroup> findByProjectAndChatSessionAndStatusOrderByUpdatedAtDesc(
		Project project,
		ChatSession chatSession,
		ToolPlanGroupStatus status
	);

	Optional<ToolPlanGroup> findFirstByProjectAndChatSessionAndStatusOrderByUpdatedAtDesc(
		Project project,
		ChatSession chatSession,
		ToolPlanGroupStatus status
	);

	Optional<ToolPlanGroup> findByIdAndProjectAndChatSession(Long id, Project project, ChatSession chatSession);
}
