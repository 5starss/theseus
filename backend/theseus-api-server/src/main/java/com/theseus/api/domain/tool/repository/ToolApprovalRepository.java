package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
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

	Optional<ToolApproval> findByToolAndRequestNumber(Tool tool, Integer requestNumber);

	Optional<ToolApproval> findTopByToolOrderByRequestNumberDesc(Tool tool);

	List<ToolApproval> findByToolAndApprovalStatusOrderByRequestNumberDesc(
		Tool tool,
		ToolApprovalStatus approvalStatus
	);

	Page<ToolApproval> findByTool_ProjectAndApprovalStatusOrderByRequestedAtDesc(
		Project project,
		ToolApprovalStatus approvalStatus,
		Pageable pageable
	);

	Optional<ToolApproval> findByIdAndTool_Project(Long id, Project project);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("""
		select toolApproval
		from ToolApproval toolApproval
		where toolApproval.tool = :tool
		order by toolApproval.requestNumber desc
	""")
	List<ToolApproval> findByToolOrderByRequestNumberDescForUpdate(@Param("tool") Tool tool);

	boolean existsByToolAndApprovalStatus(Tool tool, ToolApprovalStatus approvalStatus);
}
