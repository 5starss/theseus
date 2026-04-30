package com.theseus.api.domain.user.entity;

import com.theseus.api.common.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
	name = "users",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_users_employee_number", columnNames = "employee_number"),
		@UniqueConstraint(name = "uk_users_email", columnNames = "email")
	}
)
@Entity
public class User extends BaseEntity {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(name = "employee_number", nullable = false, length = 50)
	private String employeeNumber;

	@Column(nullable = false, length = 100)
	private String name;

	@Column(length = 100)
	private String email;

	@Column(nullable = false)
	private String password;

	@Enumerated(EnumType.STRING)
	@Column(name = "system_role", nullable = false, length = 30)
	private SystemRole systemRole;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30)
	private UserStatus status;


	@Builder
	private User(
		String employeeNumber,
		String name,
		String email,
		String password,
		SystemRole systemRole,
		UserStatus status
	) {
		this.employeeNumber = employeeNumber;
		this.name = name;
		this.email = email;
		this.password = password;
		this.systemRole = systemRole == null ? SystemRole.USER : systemRole;
		this.status = status == null ? UserStatus.ACTIVE : status;
	}

	public void update(
		String name,
		String email,
		String password,
		SystemRole systemRole
	) {
		if (name != null) {
			this.name = name;
		}
		if (email != null) {
			this.email = email;
		}
		if (password != null) {
			this.password = password;
		}
		if (systemRole != null) {
			this.systemRole = systemRole;
		}
	}

	public void updateStatus(UserStatus status) {
		this.status = status;
	}

	public boolean isSuperAdmin() {
		return SystemRole.SUPER_ADMIN.equals(systemRole);
	}


}
