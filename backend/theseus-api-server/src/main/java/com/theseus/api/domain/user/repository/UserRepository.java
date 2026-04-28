package com.theseus.api.domain.user.repository;

import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.SystemRole;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<User, Long> {

	boolean existsByEmployeeNumber(String employeeNumber);

	boolean existsByEmail(String email);

	boolean existsByEmailAndIdNot(String email, Long id);

	boolean existsBySystemRole(SystemRole systemRole);

	Optional<User> findByEmployeeNumber(String employeeNumber);
}
