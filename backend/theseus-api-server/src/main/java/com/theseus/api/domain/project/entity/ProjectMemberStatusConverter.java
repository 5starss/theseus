package com.theseus.api.domain.project.entity;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

@Converter(autoApply = true)
public class ProjectMemberStatusConverter implements AttributeConverter<ProjectMemberStatus, String> {

	@Override
	public String convertToDatabaseColumn(ProjectMemberStatus attribute) {
		if (attribute == null) {
			return null;
		}

		return attribute.getText();
	}

	@Override
	public ProjectMemberStatus convertToEntityAttribute(String dbData) {
		if (dbData == null) {
			return null;
		}

		return ProjectMemberStatus.createFrom(dbData);
	}
}
