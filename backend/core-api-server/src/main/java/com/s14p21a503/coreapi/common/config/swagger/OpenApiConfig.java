package com.s14p21a503.coreapi.common.config.swagger;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI openAPI() {
        String key = "bearerAuth";

        // Info 설정
        Info info = new Info()
                .title("stock auth/order/ledger")
                .description("<h3> 실시간 가상 주식 매매 서비스</h3>" +
                        "<ul>" +
                        "<li>실시간 주식 매매</li>" +
                        "<li>AI 에이전트</li>" +
                        "</ul>")
                .version("v1.0.0")
                .contact(new Contact()
                        .name("stock")
                        .url(""));

        // SecurityRequirement 설정 (전역 적용)
        SecurityRequirement securityRequirement = new SecurityRequirement().addList(key);

        // SecurityScheme 설정 (JWT 방식 정의)
        Components components = new Components()
                .addSecuritySchemes(key, new SecurityScheme()
                        .name(key)
                        .type(SecurityScheme.Type.HTTP)
                        .scheme("bearer")
                        .bearerFormat("JWT"));

        return new OpenAPI()
                .info(info)
                .addSecurityItem(securityRequirement)
                .components(components);
    }
}
