package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
import com.theseus.api.domain.tool.entity.ToolPlan;
import jakarta.persistence.LockModeType;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ToolApprovalRepository extends JpaRepository<ToolApproval, Long> {

	List<ToolApproval> findByToolOrderByRequestNumberDesc(Tool tool);

	List<ToolApproval> findByToolPlanOrderByRequestNumberDesc(ToolPlan toolPlan);

	Optional<ToolApproval> findByToolAndRequestNumber(Tool tool, Integer requestNumber);

	Optional<ToolApproval> findByToolPlanAndRequestNumber(ToolPlan toolPlan, Integer requestNumber);

	Optional<ToolApproval> findTopByToolOrderByRequestNumberDesc(Tool tool);

	Optional<ToolApproval> findTopByToolPlanOrderByRequestNumberDesc(ToolPlan toolPlan);

	List<ToolApproval> findByToolAndApprovalStatusOrderByRequestNumberDesc(
		Tool tool,
		ToolApprovalStatus approvalStatus
	);

	@Query(
		value = """
			select toolApproval
			from ToolApproval toolApproval
			join fetch toolApproval.tool tool
			join fetch tool.project project
			join fetch toolApproval.requestedByProjectMember requestedByProjectMember
			join fetch requestedByProjectMember.user requestedByUser
			left join fetch toolApproval.reviewedByProjectMember reviewedByProjectMember
			left join fetch reviewedByProjectMember.user reviewedByUser
			where project = :project
			order by toolApproval.requestedAt desc
		""",
		countQuery = """
			select count(toolApproval)
			from ToolApproval toolApproval
			join toolApproval.tool tool
			where tool.project = :project
		"""
	)
	Page<ToolApproval> findByProject(
		@Param("project") Project project,
		Pageable pageable
	);

	@Query(
		value = """
			select toolApproval
			from ToolApproval toolApproval
			join fetch toolApproval.tool tool
			join fetch tool.project project
			join fetch toolApproval.requestedByProjectMember requestedByProjectMember
			join fetch requestedByProjectMember.user requestedByUser
			left join fetch toolApproval.reviewedByProjectMember reviewedByProjectMember
			left join fetch reviewedByProjectMember.user reviewedByUser
			where project = :project
				and toolApproval.approvalStatus = :approvalStatus
			order by toolApproval.requestedAt desc
		""",
		countQuery = """
			select count(toolApproval)
			from ToolApproval toolApproval
			join toolApproval.tool tool
			where tool.project = :project
				and toolApproval.approvalStatus = :approvalStatus
		"""
	)
	Page<ToolApproval> findByProjectAndApprovalStatus(
		@Param("project") Project project,
		@Param("approvalStatus") ToolApprovalStatus approvalStatus,
		Pageable pageable
	);

	@Query("""
		select toolApproval
		from ToolApproval toolApproval
		join fetch toolApproval.tool tool
		join fetch tool.project project
		join fetch toolApproval.requestedByProjectMember requestedByProjectMember
		join fetch requestedByProjectMember.user requestedByUser
		left join fetch toolApproval.reviewedByProjectMember reviewedByProjectMember
		left join fetch reviewedByProjectMember.user reviewedByUser
		where toolApproval.id = :id
			and project = :project
	""")
	Optional<ToolApproval> findByIdAndToolProject(
		@Param("id") Long id,
		@Param("project") Project project
	);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select toolApproval
		from ToolApproval toolApproval
		join fetch toolApproval.tool tool
		where toolApproval.id = :id
			and tool.project = :project
	""")
	Optional<ToolApproval> findByIdAndToolProjectForUpdate(
		@Param("id") Long id,
		@Param("project") Project project
	);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select toolApproval
		from ToolApproval toolApproval
		where toolApproval.tool = :tool
		order by toolApproval.requestNumber desc
	""")
	List<ToolApproval> findByToolOrderByRequestNumberDescForUpdate(@Param("tool") Tool tool);

	boolean existsByToolAndApprovalStatus(Tool tool, ToolApprovalStatus approvalStatus);

	boolean existsByToolPlanAndApprovalStatus(ToolPlan toolPlan, ToolApprovalStatus approvalStatus);
}
