package com.theseus.api.domain.project.repository;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectStatus;
import com.theseus.api.domain.user.entity.User;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ProjectRepository extends JpaRepository<Project, Long> {

	Page<Project> findByStatus(ProjectStatus status, Pageable pageable);

	boolean existsByProjectAdminUserAndStatus(User projectAdminUser, ProjectStatus status);
}
