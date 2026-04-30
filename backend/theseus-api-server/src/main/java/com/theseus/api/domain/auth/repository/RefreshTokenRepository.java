package com.theseus.api.domain.auth.repository;

import com.theseus.api.domain.auth.entity.RefreshToken;
import com.theseus.api.domain.user.entity.User;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RefreshTokenRepository extends JpaRepository<RefreshToken, Long> {

	Optional<RefreshToken> findByTokenHash(String tokenHash);

	Optional<RefreshToken> findByUser(User user);

	void deleteByTokenHash(String tokenHash);
}
