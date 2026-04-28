package com.theseus.api.domain.project.repository;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.user.entity.User;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ProjectMemberRepository extends JpaRepository<ProjectMember, Long> {

	boolean existsByProjectAndUser(Project project, User user);

	List<ProjectMember> findByProject(Project project);

	List<ProjectMember> findByUserAndStatus(User user, ProjectMemberStatus status);

	Optional<ProjectMember> findByProjectAndUser(Project project, User user);
}
