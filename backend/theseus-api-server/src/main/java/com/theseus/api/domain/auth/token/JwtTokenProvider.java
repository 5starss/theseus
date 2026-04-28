package com.theseus.api.domain.auth.token;

import com.theseus.api.domain.user.entity.User;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import javax.crypto.SecretKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class JwtTokenProvider {

	private final SecretKey secretKey;
	private final long accessTokenExpirationMillis;

	public JwtTokenProvider(
		@Value("${jwt.secret}") String secret,
		@Value("${jwt.access-token-expiration-millis}") long accessTokenExpirationMillis
	) {
		this.secretKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
		this.accessTokenExpirationMillis = accessTokenExpirationMillis;
	}

	public String createAccessToken(User user) {
		Date now = new Date();
		Date expiresAt = new Date(now.getTime() + accessTokenExpirationMillis);

		return Jwts.builder()
			.subject(String.valueOf(user.getId()))
			.claim("role", user.getSystemRole().name())
			.issuedAt(now)
			.expiration(expiresAt)
			.signWith(secretKey)
			.compact();
	}

	public Long getUserId(String token) {
		Claims claims = parseClaims(token);

		return Long.valueOf(claims.getSubject());
	}

	public boolean validateToken(String token) {
		parseClaims(token);

		return true;
	}

	private Claims parseClaims(String token) {
		return Jwts.parser()
			.verifyWith(secretKey)
			.build()
			.parseSignedClaims(token)
			.getPayload();
	}
}
