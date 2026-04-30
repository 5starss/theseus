package com.theseus.api.domain.chat.dto.request;

import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class ChatSessionCreateRequest {

	@Size(max = 150)
	private String title;

	public ChatSession toEntity(Project project, ProjectMember projectMember) {
		return ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title(title)
			.build();
	}
}
