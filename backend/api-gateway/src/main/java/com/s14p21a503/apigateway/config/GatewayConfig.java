package com.s14p21a503.apigateway.config;

import com.s14p21a503.apigateway.filter.JwtAuthenticationFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class GatewayConfig {

    @Value("${service.core.url}")
    private String coreUrl;

    @Value("${service.core.api-docs-url}")
    private String coreApiDocsUrl;

    @Value("${service.market.url}")
    private String marketUrl;

    @Value("${service.market.ws-url}")
    private String marketWsUrl;

    @Value("${service.market.api-docs-url}")
    private String marketApiDocsUrl;

    @Value("${service.ai.url}")
    private String aiUrl;

    @Value("${service.ai.api-docs-url}")
    private String aiApiDocsUrl;

    @Bean
    public RouteLocator customRouteLocator(RouteLocatorBuilder builder, JwtAuthenticationFilter jwtFilter) {
        return builder.routes()
            // 1. Core API Server
            .route("core-route", r -> r.path("/api/v1/core/**")
                .filters(f -> f
                    .filter(jwtFilter)
                    .rewritePath("/api/v1/core/(?<segment>.*)", "/api/v1/${segment}")
                )
                .uri(coreUrl))

            // 2. Market Server
            .route("market-route", r -> r.path("/api/v1/market/**")
                .filters(f -> f
                    .filter(jwtFilter)
                    .rewritePath("/api/v1/market/(?<segment>.*)", "/api/v1/${segment}")
                )
                .uri(marketUrl))

            // 3. Market WebSocket Service
            .route("market-ws-route", r -> r.path("/v1/stocks/ws")
                .filters(f -> f.filter(jwtFilter))
                .uri(marketWsUrl))

            // 4. AI Service
            .route("ai-route", r -> r.path("/api/v1/ai/**")
                .filters(f -> f
                    .filter(jwtFilter)
                    .rewritePath("/api/v1/ai/(?<segment>.*)", "/v1/${segment}")
                )
                .uri(aiUrl))

            // --- Swagger API Docs Routes ---
            .route("core-api-docs", r -> r.path("/v3/api-docs/core-api")
                .filters(f -> f.rewritePath("/v3/api-docs/core-api", "/v3/api-docs"))
                .uri(coreApiDocsUrl))
            
            .route("market-api-docs", r -> r.path("/v3/api-docs/market")
                .filters(f -> f.rewritePath("/v3/api-docs/market", "/v3/api-docs"))
                .uri(marketApiDocsUrl))
            
            .route("ai-api-docs", r -> r.path("/v3/api-docs/ai")
                .filters(f -> f.rewritePath("/v3/api-docs/ai", "/openapi.json"))
                .uri(aiApiDocsUrl))
            // -------------------------------

            .build();
    }
}
