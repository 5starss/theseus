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
        String jwtkey = "bearerAuth";
        String userIdKey = "X-User-Id";

        // Info 설정
        Info info = new Info()
                .title("stock auth/oder/ledger")
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
        SecurityRequirement securityRequirement = new SecurityRequirement()
                .addList(jwtkey)
                .addList(userIdKey);

        // SecurityScheme 설정
        Components components = new Components()
                // 1. JWT 설정
                .addSecuritySchemes(jwtkey, new SecurityScheme()
                        .name(jwtkey)
                        .type(SecurityScheme.Type.HTTP)
                        .scheme("bearer")
                        .bearerFormat("JWT"))
                // 2. X-User-Id 헤더 설정
                .addSecuritySchemes(userIdKey, new SecurityScheme()
                        .name(userIdKey)
                        .type(SecurityScheme.Type.APIKEY) // APIKEY 방식
                        .in(SecurityScheme.In.HEADER) // HEADER 위치 설정
                        .description("게이트웨이에서 주입되는 사용자 ID"));

        return new OpenAPI()
                .info(info)
                .addSecurityItem(securityRequirement)
                .components(components);
    }
}
