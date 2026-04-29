package com.theseus.api.domain.auth.entity;

import com.theseus.api.common.entity.BaseEntity;
import com.theseus.api.domain.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
	name = "refresh_tokens",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_refresh_tokens_user", columnNames = "user_id"),
		@UniqueConstraint(name = "uk_refresh_tokens_token_hash", columnNames = "token_hash")
	}
)
@Entity
public class RefreshToken extends BaseEntity {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@OneToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@Column(name = "token_hash", nullable = false, length = 64)
	private String tokenHash;

	@Column(name = "expires_at", nullable = false)
	private LocalDateTime expiresAt;

	@Builder
	private RefreshToken(User user, String tokenHash, LocalDateTime expiresAt) {
		this.user = user;
		this.tokenHash = tokenHash;
		this.expiresAt = expiresAt;
	}

	public void update(String tokenHash, LocalDateTime expiresAt) {
		this.tokenHash = tokenHash;
		this.expiresAt = expiresAt;
	}

	public boolean isExpired(LocalDateTime now) {
		return expiresAt.isBefore(now) || expiresAt.isEqual(now);
	}
}
