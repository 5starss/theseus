package com.s14p21a503.coreapi.common.log;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.HandlerMapping;
import org.springframework.web.util.ContentCachingResponseWrapper;
import org.springframework.web.util.WebUtils;

import java.nio.charset.StandardCharsets;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class LoggingInterceptor implements HandlerInterceptor {

    private final ObjectMapper objectMapper;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {

        // PathVariable 로그
        if (handler instanceof HandlerMethod) {
            Map<String, String> pathVariables = (Map<String, String>) request.getAttribute(HandlerMapping.URI_TEMPLATE_VARIABLES_ATTRIBUTE);
            if (pathVariables != null && !pathVariables.isEmpty()) {
                log.info("📦 [{}] {} \npathVars : {}", request.getMethod(), request.getRequestURI(), pathVariables);
            }
        }

        // QueryParams 로그
        if (request.getParameterNames().hasMoreElements()) {
            log.info("📦️ [{}] {} \nqueryParams : {}", request.getMethod(), request.getRequestURI(), getRequestParams(request));
        }

        // Body 로그 (WebUtils로 래퍼 찾기)
        CustomHttpRequestWrapper wrapper = WebUtils.getNativeRequest(request, CustomHttpRequestWrapper.class);
        if (wrapper != null) {
            String body = new String(wrapper.getRequestBody());
            if (!body.isBlank()) {
                try {
                    Object json = objectMapper.readValue(body, Object.class);
                    String prettyBody = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(json);
                    log.info("📦 [{}] {} \nbody : {}", request.getMethod(), request.getRequestURI(), prettyBody);
                } catch (Exception e) {
                    log.info("📦 [{}] {} \nbody(raw) : {}", request.getMethod(), request.getRequestURI(), body);
                }
            }
        }

        request.setAttribute("startTime", System.currentTimeMillis());
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) throws Exception {
        Long start = (Long) request.getAttribute("startTime");
        long duration = System.currentTimeMillis() - (start != null ? start : 0L);
        int status = response.getStatus();

        // 응답 Body 가져오기 (에러 메시지 확인용)
        String responseBody = "";
        ContentCachingResponseWrapper responseWrapper = WebUtils.getNativeResponse(response, ContentCachingResponseWrapper.class);
        if (responseWrapper != null) {
            byte[] buf = responseWrapper.getContentAsByteArray();
            if (buf.length > 0) {
                // 너무 길면 자르기 가능
                responseBody = new String(buf, StandardCharsets.UTF_8);
            }
        }

        if (status >= 400) {
            log.error("❌ [{}] {} request failed - {}ms | status={}", request.getMethod(), request.getRequestURI(), duration, status);
        } else {
            log.info("✅ [{}] {} request completed - {}ms | status={}", request.getMethod(), request.getRequestURI(), duration, status);
        }
    }

    private Map<String, String> getRequestParams(HttpServletRequest request) {
        Map<String, String> paramMap = new HashMap<>();
        Enumeration<String> parameterNames = request.getParameterNames();
        while (parameterNames.hasMoreElements()) {
            String paramName = parameterNames.nextElement();
            paramMap.put(paramName, request.getParameter(paramName));
        }
        return paramMap;
    }
}
