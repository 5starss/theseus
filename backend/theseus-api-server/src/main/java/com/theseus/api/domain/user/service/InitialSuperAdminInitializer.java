package com.theseus.api.domain.user.service;

import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.dao.DataAccessException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

@Slf4j
@RequiredArgsConstructor
@Component
public class InitialSuperAdminInitializer implements ApplicationRunner {

	private final UserRepository userRepository;
	private final PasswordEncoder passwordEncoder;

	@Value("${INITIAL_ADMIN_EMPLOYEE_NUMBER:}")
	private String initialAdminEmployeeNumber;

	@Value("${INITIAL_ADMIN_NAME:}")
	private String initialAdminName;

	@Value("${INITIAL_ADMIN_EMAIL:}")
	private String initialAdminEmail;

	@Value("${INITIAL_ADMIN_PASSWORD:}")
	private String initialAdminPassword;

	@Override
	public void run(ApplicationArguments args) {
		try {
			if (userRepository.existsBySystemRole(SystemRole.SUPER_ADMIN)) {
				return;
			}

			if (!hasInitialAdminRequiredValues()) {
				log.info(">>>> Initial SUPER_ADMIN was not created because required environment values are missing.");
				return;
			}

			User initialSuperAdmin = User.builder()
				.employeeNumber(initialAdminEmployeeNumber)
				.name(initialAdminName)
				.email(hasText(initialAdminEmail) ? initialAdminEmail : null)
				.password(passwordEncoder.encode(initialAdminPassword))
				.systemRole(SystemRole.SUPER_ADMIN)
				.status(UserStatus.ACTIVE)
				.build();

			userRepository.save(initialSuperAdmin);
			log.info(">>>> Initial SUPER_ADMIN has been created. employeeNumber={}", initialAdminEmployeeNumber);
		} catch (DataAccessException dataAccessException) {
			log.warn(">>>> Initial SUPER_ADMIN creation was skipped because the users table is not ready.");
		}
	}

	private boolean hasInitialAdminRequiredValues() {
		return hasText(initialAdminEmployeeNumber)
			&& hasText(initialAdminName)
			&& hasText(initialAdminPassword);
	}

	private boolean hasText(String value) {
		return StringUtils.hasText(value);
	}
}
