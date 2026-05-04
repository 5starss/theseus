package com.theseus.api.common.config.security;

import com.theseus.api.common.exception.ErrorCode;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

@RequiredArgsConstructor
@Component
public class InternalApiAuthenticationFilter extends OncePerRequestFilter {

	private static final String INTERNAL_API_PATH_PREFIX = "/api/internal/";
	private static final String INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key";
	private static final String INTERNAL_API_PRINCIPAL = "internal-api";
	private static final String INTERNAL_ROLE = "ROLE_INTERNAL";

	@Value("${internal.api-key:}")
	private String internalApiKey;

	@Override
	protected boolean shouldNotFilter(HttpServletRequest request) {
		return !request.getRequestURI().startsWith(INTERNAL_API_PATH_PREFIX);
	}

	@Override
	protected void doFilterInternal(
		HttpServletRequest request,
		HttpServletResponse response,
		FilterChain filterChain
	) throws ServletException, IOException {
		String requestApiKey = request.getHeader(INTERNAL_API_KEY_HEADER);

		if (!StringUtils.hasText(internalApiKey) || !internalApiKey.equals(requestApiKey)) {
			SecurityContextHolder.clearContext();
			writeUnauthorizedResponse(response);
			return;
		}

		UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
			INTERNAL_API_PRINCIPAL,
			null,
			List.of(new SimpleGrantedAuthority(INTERNAL_ROLE))
		);
		SecurityContextHolder.getContext().setAuthentication(authentication);

		filterChain.doFilter(request, response);
	}

	private void writeUnauthorizedResponse(HttpServletResponse response) throws IOException {
		ErrorCode errorCode = ErrorCode.INTERNAL_API_UNAUTHORIZED;

		response.setStatus(errorCode.getStatus().value());
		response.setContentType(MediaType.APPLICATION_JSON_VALUE);
		response.setCharacterEncoding(StandardCharsets.UTF_8.name());
		response.getWriter().write("""
			{"isSuccess":false,"code":"%s","message":"%s"}
			""".formatted(errorCode.getCode(), errorCode.getMessage()).trim());
	}
}
