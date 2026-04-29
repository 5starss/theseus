package com.theseus.api.domain.chat.repository;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ChatSessionRepository extends JpaRepository<ChatSession, Long> {

	List<ChatSession> findByProjectAndProjectMemberOrderByUpdatedAtDesc(
		Project project,
		ProjectMember projectMember
	);

	List<ChatSession> findByProjectMemberAndClosedAtIsNullOrderByUpdatedAtDesc(ProjectMember projectMember);

	Optional<ChatSession> findByIdAndProjectMember(Long id, ProjectMember projectMember);
}
