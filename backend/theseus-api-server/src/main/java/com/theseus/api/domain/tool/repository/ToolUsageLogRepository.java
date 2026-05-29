package com.theseus.api.domain.tool.repository;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.tool.entity.ToolUsageLog;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ToolUsageLogRepository extends JpaRepository<ToolUsageLog, Long> {

	List<ToolUsageLog> findByProjectOrderByUsedAtDesc(Project project);
}
