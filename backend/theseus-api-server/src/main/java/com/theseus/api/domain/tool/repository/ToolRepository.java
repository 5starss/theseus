package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolStatus;
import jakarta.persistence.LockModeType;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ToolRepository extends JpaRepository<Tool, Long> {

	List<Tool> findByChatSessionOrderByUpdatedAtDesc(ChatSession chatSession);

	List<Tool> findByChatSessionAndStatusNotOrderByUpdatedAtDesc(ChatSession chatSession, ToolStatus status);

	List<Tool> findByProjectAndStatusOrderByUpdatedAtDesc(Project project, ToolStatus status);

	List<Tool> findByProjectAndStatusNotOrderByUpdatedAtDesc(Project project, ToolStatus status);

	@Query(
		value = """
			select tool
			from Tool tool
			join fetch tool.chatSession
			join fetch tool.createdByProjectMember createdByProjectMember
			join fetch createdByProjectMember.user
			where tool.project = :project
				and tool.status = :status
				and (tool.toolGrade is null or tool.toolGrade <= :accessLevel)
			order by tool.updatedAt desc
		""",
		countQuery = """
			select count(tool)
			from Tool tool
			where tool.project = :project
				and tool.status = :status
				and (tool.toolGrade is null or tool.toolGrade <= :accessLevel)
		"""
	)
	Page<Tool> findAccessibleByProjectAndStatus(
		@Param("project") Project project,
		@Param("status") ToolStatus status,
		@Param("accessLevel") Integer accessLevel,
		Pageable pageable
	);

	Optional<Tool> findByIdAndProject(Long id, Project project);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select tool
		from Tool tool
		where tool.id = :id
			and tool.project = :project
		""")
	Optional<Tool> findByIdAndProjectForUpdate(
		@Param("id") Long id,
		@Param("project") Project project
	);

	Optional<Tool> findByIdAndProjectAndStatusNot(Long id, Project project, ToolStatus status);

	Optional<Tool> findByIdAndStatusNot(Long id, ToolStatus status);

	Optional<Tool> findByIdAndProjectAndChatSession(Long id, Project project, ChatSession chatSession);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select tool
		from Tool tool
		where tool.id = :id
			and tool.project = :project
			and tool.chatSession = :chatSession
		""")
	Optional<Tool> findByIdAndProjectAndChatSessionForUpdate(
		@Param("id") Long id,
		@Param("project") Project project,
		@Param("chatSession") ChatSession chatSession
	);

	boolean existsByProjectAndFileName(Project project, String fileName);

	boolean existsByProjectAndFileNameAndIdNot(Project project, String fileName, Long id);
}
