package com.theseus.api.common.config.swagger;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenAPI configuration for Swagger UI and JWT Bearer authentication testing.
 */
@ConditionalOnProperty(prefix = "springdoc.api-docs", name = "enabled", havingValue = "true", matchIfMissing = true)
@Configuration
public class OpenApiConfig {

	private static final String JWT_SECURITY_SCHEME_NAME = "bearerAuth";

	/**
	 * Creates OpenAPI metadata with a JWT Bearer Token security scheme.
	 *
	 * @return OpenAPI configuration with JWT authentication metadata
	 */
	@Bean
	public OpenAPI openApi() {
		Info info = new Info()
			.title("Theseus API")
			.description("""
				<h3>Theseus API Server</h3>
				<ul>
					<li>Project collaboration API</li>
					<li>AI agent API</li>
				</ul>
				""")
			.version("v1.0.0")
			.contact(new Contact()
				.name("Theseus")
				.url(""));

		SecurityRequirement securityRequirement = new SecurityRequirement()
			.addList(JWT_SECURITY_SCHEME_NAME);

		Components components = new Components()
			.addSecuritySchemes(JWT_SECURITY_SCHEME_NAME, createJwtSecurityScheme());

		return new OpenAPI()
			.info(info)
			.addSecurityItem(securityRequirement)
			.components(components);
	}

	private SecurityScheme createJwtSecurityScheme() {
		return new SecurityScheme()
			.name(JWT_SECURITY_SCHEME_NAME)
			.type(SecurityScheme.Type.HTTP)
			.scheme("bearer")
			.bearerFormat("JWT");
	}
}
