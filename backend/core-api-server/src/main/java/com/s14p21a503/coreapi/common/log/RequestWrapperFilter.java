package com.s14p21a503.coreapi.common.log;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.util.ContentCachingResponseWrapper;

import java.io.IOException;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE) // 가장 먼저 실행되어야 함
public class RequestWrapperFilter implements Filter {

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        if (request instanceof HttpServletRequest httpRequest && response instanceof HttpServletResponse httpResponse) {
            String path = httpRequest.getRequestURI();
            String contentType = httpRequest.getContentType();

            // SSE 구독 경로는 래핑 제외 (버퍼링 방지)
            if (path.contains("/notifications/subscribe")) {
                chain.doFilter(request, response);
                return;
            }

            if (contentType != null && contentType.toLowerCase().contains(MediaType.MULTIPART_FORM_DATA_VALUE)) {
                chain.doFilter(request, response);
                return;
            }

            // 1. Request 래핑 (Body 읽기 가능하게)
            CustomHttpRequestWrapper wrappedRequest = new CustomHttpRequestWrapper(httpRequest);

            // 2. Response 래핑 (나중에 응답 Body 읽기 가능하게)
            ContentCachingResponseWrapper wrappedResponse = new ContentCachingResponseWrapper(httpResponse);

            // 3. 체인 실행
            chain.doFilter(wrappedRequest, wrappedResponse);

            // 4. 래핑된 응답을 실제 클라이언트에게 전송
            wrappedResponse.copyBodyToResponse();
        } else {
            chain.doFilter(request, response);
        }
    }
}
