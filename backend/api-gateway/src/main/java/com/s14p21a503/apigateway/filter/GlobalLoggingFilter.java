package com.s14p21a503.apigateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.UUID;

@Slf4j
@Component
public class GlobalLoggingFilter implements GlobalFilter, Ordered {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        // 1. Create trace ID
        String traceId = UUID.randomUUID().toString();
        long startTime = System.currentTimeMillis();

        // 2. Setup Mutated Request with X-Request-Id
        ServerHttpRequest request = exchange.getRequest();
        ServerHttpRequest mutatedRequest = request.mutate()
                .header("X-Request-Id", traceId)
                .build();

        String ip = request.getRemoteAddress() != null ? 
                        request.getRemoteAddress().getAddress().getHostAddress() : "UNKNOWN";

        log.info("[{}] Request: {} {}, Client IP: {}", 
                traceId, 
                request.getMethod(), 
                request.getURI().getPath(), 
                ip);

        // 3. Chain and post-log
        return chain.filter(exchange.mutate().request(mutatedRequest).build())
                .then(Mono.fromRunnable(() -> {
                    ServerHttpResponse response = exchange.getResponse();
                    long latency = System.currentTimeMillis() - startTime;
                    log.info("[{}] Response: Status {}, Latency: {} ms",
                            traceId,
                            response.getStatusCode(),
                            latency);
                }));
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
