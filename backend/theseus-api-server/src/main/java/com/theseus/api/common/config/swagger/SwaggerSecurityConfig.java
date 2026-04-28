package com.theseus.api.common.config.swagger;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Swagger 및 개발 단계 API 테스트를 위한 Security 설정입니다.
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
	 * 개발 단계에서는 Swagger 테스트 편의를 위해 모든 요청을 허용합니다.
	 *
	 * @param http Spring Security HTTP 설정 객체
	 * @return SecurityFilterChain
	 * @throws Exception Security 설정 실패 시 발생
	 */
	@Bean
	public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
		http
				.csrf(csrf -> csrf.disable())
				.authorizeHttpRequests(auth -> auth
						.anyRequest().permitAll())
				.formLogin(formLogin -> formLogin.disable())
				.httpBasic(httpBasic -> httpBasic.disable());

		return http.build();
	}
}