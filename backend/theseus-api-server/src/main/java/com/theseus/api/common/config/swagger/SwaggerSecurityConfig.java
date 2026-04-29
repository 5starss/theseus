package com.theseus.api.common.config.swagger;

import com.theseus.api.domain.auth.token.JwtAuthenticationFilter;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "springdoc.swagger-ui", name = "enabled", havingValue = "true", matchIfMissing = true)
@Configuration
public class SwaggerSecurityConfig {

	private static final String[] SWAGGER_PATHS = {
		"/swagger-ui.html",
		"/swagger-ui/**",
		"/v3/api-docs",
		"/v3/api-docs/**"
	};

	private final JwtAuthenticationFilter jwtAuthenticationFilter;

	@Bean
	@Order(1)
	public SecurityFilterChain swaggerSecurityFilterChain(HttpSecurity http) throws Exception {
		http
			.securityMatcher(SWAGGER_PATHS)
			.csrf(csrf -> csrf.disable())
			.sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
			.authorizeHttpRequests(auth -> auth
				.requestMatchers(SWAGGER_PATHS).permitAll()
				.anyRequest().authenticated())
			.formLogin(formLogin -> formLogin.disable())
			.httpBasic(httpBasic -> httpBasic.disable())
			.addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

		return http.build();
	}
}
