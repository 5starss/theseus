package com.theseus.api.domain.chat.repository;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import java.util.List;
import java.util.Optional;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ChatSessionRepository extends JpaRepository<ChatSession, Long> {

	List<ChatSession> findByProjectAndProjectMemberOrderByUpdatedAtDesc(
		Project project,
		ProjectMember projectMember
	);

	Page<ChatSession> findByProjectAndProjectMemberOrderByUpdatedAtDesc(
		Project project,
		ProjectMember projectMember,
		Pageable pageable
	);

	List<ChatSession> findByProjectMemberAndClosedAtIsNullOrderByUpdatedAtDesc(ProjectMember projectMember);

	Optional<ChatSession> findByIdAndProjectMember(Long id, ProjectMember projectMember);

	Optional<ChatSession> findByIdAndProject(Long id, Project project);

	Optional<ChatSession> findByIdAndProjectAndProjectMember(
		Long id,
		Project project,
		ProjectMember projectMember
	);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select chatSession
		from ChatSession chatSession
		where chatSession.id = :id
			and chatSession.project = :project
			and chatSession.projectMember = :projectMember
		""")
	Optional<ChatSession> findByIdAndProjectAndProjectMemberForUpdate(
		@Param("id") Long id,
		@Param("project") Project project,
		@Param("projectMember") ProjectMember projectMember
	);
}
