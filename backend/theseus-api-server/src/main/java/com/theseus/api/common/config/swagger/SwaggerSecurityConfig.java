package com.theseus.api.common.config.swagger;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Security configuration that allows Swagger UI and OpenAPI document access when Swagger is enabled.
 */
@ConditionalOnProperty(prefix = "springdoc.swagger-ui", name = "enabled", havingValue = "true", matchIfMissing = true)
@Configuration
public class SwaggerSecurityConfig {

	private static final String[] SWAGGER_PATHS = {
		"/swagger-ui.html",
		"/swagger-ui/**",
		"/v3/api-docs",
		"/v3/api-docs/**"
	};

	/**
	 * Allows Swagger paths without authentication and keeps authentication required for other requests.
	 *
	 * @param httpSecurity Spring Security HTTP configuration
	 * @return SecurityFilterChain with Swagger path access rules
	 * @throws Exception when Spring Security configuration fails
	 */
	@Bean
	public SecurityFilterChain swaggerSecurityFilterChain(HttpSecurity httpSecurity) throws Exception {
		return httpSecurity
			.csrf(AbstractHttpConfigurer::disable)
			.authorizeHttpRequests(authorizationManagerRequestMatcherRegistry ->
				authorizationManagerRequestMatcherRegistry
					.requestMatchers(SWAGGER_PATHS).permitAll()
					.anyRequest().authenticated())
			.formLogin(Customizer.withDefaults())
			.httpBasic(Customizer.withDefaults())
			.build();
	}
}
