package com.theseus.api.domain.auth.token;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@RequiredArgsConstructor
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

	private static final String AUTHORIZATION_HEADER = "Authorization";
	private static final String BEARER_PREFIX = "Bearer ";
	private static final String ROLE_PREFIX = "ROLE_";
	private static final String INTERNAL_API_PATH_PREFIX = "/api/internal/";

	private final JwtTokenProvider jwtTokenProvider;
	private final UserRepository userRepository;

	@Override
	protected boolean shouldNotFilter(HttpServletRequest request) {
		return request.getRequestURI().startsWith(INTERNAL_API_PATH_PREFIX);
	}

	@Override
	protected void doFilterInternal(
		HttpServletRequest request,
		HttpServletResponse response,
		FilterChain filterChain
	) throws ServletException, IOException {
		String token = resolveToken(request);

		if (token != null && SecurityContextHolder.getContext().getAuthentication() == null) {
			authenticate(token);
		}

		filterChain.doFilter(request, response);
	}

	private String resolveToken(HttpServletRequest request) {
		String authorization = request.getHeader(AUTHORIZATION_HEADER);

		if (authorization == null || !authorization.startsWith(BEARER_PREFIX)) {
			return null;
		}

		return authorization.substring(BEARER_PREFIX.length());
	}

	private void authenticate(String token) {
		try {
			jwtTokenProvider.validateToken(token);
			Long userId = jwtTokenProvider.getUserId(token);
			userRepository.findById(userId).ifPresent(this::setAuthentication);
		} catch (JwtException | IllegalArgumentException | BusinessException exception) {
			SecurityContextHolder.clearContext();
		}
	}

	private void setAuthentication(User user) {
		AuthenticatedUser authenticatedUser = new AuthenticatedUser(
			user.getId(),
			user.getEmployeeNumber(),
			user.getName(),
			user.getSystemRole()
		);
		SimpleGrantedAuthority authority = new SimpleGrantedAuthority(ROLE_PREFIX + user.getSystemRole().name());
		UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
			authenticatedUser,
			null,
			List.of(authority)
		);

		SecurityContextHolder.getContext().setAuthentication(authentication);
	}
}
