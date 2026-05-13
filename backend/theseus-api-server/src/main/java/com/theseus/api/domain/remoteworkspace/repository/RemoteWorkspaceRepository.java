package com.theseus.api.domain.remoteworkspace.repository;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspaceStatus;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RemoteWorkspaceRepository extends JpaRepository<RemoteWorkspace, Long> {

	List<RemoteWorkspace> findByProjectAndStatusNotOrderByUpdatedAtDesc(Project project, RemoteWorkspaceStatus status);

	Optional<RemoteWorkspace> findByIdAndProjectAndStatusNot(
		Long id,
		Project project,
		RemoteWorkspaceStatus status
	);
}
