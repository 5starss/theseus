package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.ToolUsageLog;
import com.theseus.api.domain.tool.entity.ToolUsageStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ToolUsageLogRepository extends JpaRepository<ToolUsageLog, Long> {

	Page<ToolUsageLog> findByProjectOrderByUsedAtDesc(Project project, Pageable pageable);

	Page<ToolUsageLog> findByProjectAndStatusOrderByUsedAtDesc(
		Project project,
		ToolUsageStatus status,
		Pageable pageable
	);
}
