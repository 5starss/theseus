package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolStatus;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ToolRepository extends JpaRepository<Tool, Long> {

	List<Tool> findByChatSessionOrderByUpdatedAtDesc(ChatSession chatSession);

	List<Tool> findByProjectAndStatusOrderByUpdatedAtDesc(Project project, ToolStatus status);

	Optional<Tool> findByIdAndProject(Long id, Project project);

	Optional<Tool> findByIdAndProjectAndChatSession(Long id, Project project, ChatSession chatSession);

	boolean existsByProjectAndFileName(Project project, String fileName);
}
