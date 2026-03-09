package com.s14p21a503.apigateway.filter;

import com.s14p21a503.apigateway.config.JwtProperties;
import com.s14p21a503.apigateway.util.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilter;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter implements GatewayFilter {

    private final JwtUtil jwtUtil;
    private final JwtProperties jwtProperties;

    private final AntPathMatcher pathMatcher = new AntPathMatcher();

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getURI().getPath();

        boolean isWhitelisted = jwtProperties.getWhitelist().stream()
                .anyMatch(pattern -> pathMatcher.match(pattern, path));

        // 1. Extract Token (Header or Query parameter for WS)
        String token = extractToken(request);
        String userId = null;

        if (token != null && jwtUtil.validateToken(token)) {
            try {
                userId = jwtUtil.getUserIdFromToken(token);
            } catch (Exception e) {
                log.error("Could not extract user info from token", e);
            }
        }

        if (userId != null && !userId.trim().isEmpty()) {
            // Token is valid -> Inject X-USER-ID
            ServerHttpRequest mutatedRequest = exchange.getRequest().mutate()
                    .headers(httpHeaders -> httpHeaders.remove("X-USER-ID"))
                    .header("X-USER-ID", userId)
                    .build();
            return chain.filter(exchange.mutate().request(mutatedRequest).build());
        }

        // Token is missing or invalid
        if (isWhitelisted) {
            // Pass without X-USER-ID (Anonymous)
            ServerHttpRequest mutatedRequest = exchange.getRequest().mutate()
                    .headers(httpHeaders -> httpHeaders.remove("X-USER-ID"))
                    .build();
            return chain.filter(exchange.mutate().request(mutatedRequest).build());
        } else {
            // Secured endpoint -> Reject
            log.warn("Missing or invalid JWT token for secured path: {}", path);
            return onError(exchange, HttpStatus.UNAUTHORIZED);
        }
    }

    private String extractToken(ServerHttpRequest request) {
        String authHeader = request.getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7);
        }
        // Fallback to query parameter (often used for WebSockets since JS API cannot set headers)
        return request.getQueryParams().getFirst("token");
    }

    private Mono<Void> onError(ServerWebExchange exchange, HttpStatus httpStatus) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(httpStatus);
        return response.setComplete();
    }
}
