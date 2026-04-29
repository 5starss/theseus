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

	private static final String TOKEN_TYPE_CLAIM = "tokenType";
	private static final String ACCESS_TOKEN_TYPE = "access";
	private static final String REFRESH_TOKEN_TYPE = "refresh";

	private final SecretKey secretKey;
	private final long accessTokenExpirationMillis;
	private final long refreshTokenExpirationMillis;

	public JwtTokenProvider(
		@Value("${jwt.secret}") String secret,
		@Value("${jwt.access-token-expiration-millis}") long accessTokenExpirationMillis,
		@Value("${jwt.refresh-token-expiration-millis}") long refreshTokenExpirationMillis
	) {
		this.secretKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
		this.accessTokenExpirationMillis = accessTokenExpirationMillis;
		this.refreshTokenExpirationMillis = refreshTokenExpirationMillis;
	}

	public String createAccessToken(User user) {
		return createToken(user, accessTokenExpirationMillis, ACCESS_TOKEN_TYPE);
	}

	public String createRefreshToken(User user) {
		return createToken(user, refreshTokenExpirationMillis, REFRESH_TOKEN_TYPE);
	}

	public Long getUserId(String token) {
		Claims claims = parseClaims(token);

		return Long.valueOf(claims.getSubject());
	}

	public boolean validateToken(String token) {
		return validateAccessToken(token);
	}

	public boolean validateAccessToken(String token) {
		validateTokenType(token, ACCESS_TOKEN_TYPE);

		return true;
	}

	public boolean validateRefreshToken(String token) {
		validateTokenType(token, REFRESH_TOKEN_TYPE);

		return true;
	}

	public long getRefreshTokenExpirationMillis() {
		return refreshTokenExpirationMillis;
	}

	private String createToken(User user, long expirationMillis, String tokenType) {
		Date now = new Date();
		Date expiresAt = new Date(now.getTime() + expirationMillis);

		return Jwts.builder()
			.subject(String.valueOf(user.getId()))
			.claim("role", user.getSystemRole().name())
			.claim(TOKEN_TYPE_CLAIM, tokenType)
			.issuedAt(now)
			.expiration(expiresAt)
			.signWith(secretKey)
			.compact();
	}

	private void validateTokenType(String token, String tokenType) {
		Claims claims = parseClaims(token);

		if (!tokenType.equals(claims.get(TOKEN_TYPE_CLAIM, String.class))) {
			throw new IllegalArgumentException("지원하지 않는 토큰 타입입니다.");
		}
	}

	private Claims parseClaims(String token) {
		return Jwts.parser()
			.verifyWith(secretKey)
			.build()
			.parseSignedClaims(token)
			.getPayload();
	}
}
