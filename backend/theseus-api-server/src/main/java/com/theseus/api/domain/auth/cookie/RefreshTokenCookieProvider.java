package com.theseus.api.domain.auth.cookie;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.util.Arrays;
import lombok.Getter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

@Getter
@Component
public class RefreshTokenCookieProvider {

	private final String cookieName;
	private final boolean secure;
	private final String sameSite;
	private final long expirationMillis;

	public RefreshTokenCookieProvider(
		@Value("${jwt.refresh-token-cookie-name:refreshToken}") String cookieName,
		@Value("${jwt.refresh-token-cookie-secure:false}") boolean secure,
		@Value("${jwt.refresh-token-cookie-same-site:Lax}") String sameSite,
		@Value("${jwt.refresh-token-expiration-millis}") long expirationMillis
	) {
		this.cookieName = cookieName;
		this.secure = secure;
		this.sameSite = sameSite;
		this.expirationMillis = expirationMillis;
	}

	public ResponseCookie createCookie(String refreshToken) {
		return ResponseCookie.from(cookieName, refreshToken)
			.httpOnly(true)
			.secure(secure)
			.sameSite(sameSite)
			.path("/")
			.maxAge(Duration.ofMillis(expirationMillis))
			.build();
	}

	public ResponseCookie createExpiredCookie() {
		return ResponseCookie.from(cookieName, "")
			.httpOnly(true)
			.secure(secure)
			.sameSite(sameSite)
			.path("/")
			.maxAge(Duration.ZERO)
			.build();
	}

	public String resolveRefreshToken(HttpServletRequest request) {
		Cookie[] cookies = request.getCookies();

		if (cookies == null) {
			return null;
		}

		return Arrays.stream(cookies)
			.filter(cookie -> cookieName.equals(cookie.getName()))
			.map(Cookie::getValue)
			.findFirst()
			.orElse(null);
	}
}
