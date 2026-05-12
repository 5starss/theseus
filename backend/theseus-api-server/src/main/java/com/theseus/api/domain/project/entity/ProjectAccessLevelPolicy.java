package com.theseus.api.domain.project.entity;

public final class ProjectAccessLevelPolicy {

	public static final int DEFAULT_MEMBER_ACCESS_LEVEL = 1;
	public static final int MAX_MEMBER_ACCESS_LEVEL = 99;
	public static final int ADMIN_ACCESS_LEVEL = 100;

	private ProjectAccessLevelPolicy() {
	}

	public static int resolveAccessLevel(ProjectRole projectRole, Integer accessLevel) {
		if (ProjectRole.ADMIN.equals(projectRole)) {
			return ADMIN_ACCESS_LEVEL;
		}
		if (accessLevel == null) {
			return DEFAULT_MEMBER_ACCESS_LEVEL;
		}
		return accessLevel;
	}

	public static boolean isMemberAccessLevel(Integer accessLevel) {
		return accessLevel != null
			&& accessLevel >= DEFAULT_MEMBER_ACCESS_LEVEL
			&& accessLevel <= MAX_MEMBER_ACCESS_LEVEL;
	}
}
