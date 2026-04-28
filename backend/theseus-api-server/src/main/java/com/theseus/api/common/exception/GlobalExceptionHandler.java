package com.theseus.api.common.exception;

import com.theseus.api.common.response.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    // CustomException 핸들링
    @ExceptionHandler(CustomException.class)
    public ResponseEntity<ApiResponse<Void>> handleCustomException(CustomException e, HttpServletRequest request) {
        log.warn("[CustomException] {} {} - Code: {}, Message: {}", 
                request.getMethod(), request.getRequestURI(), e.getErrorCode().getCode(), e.getMessage());
        return ApiResponse.onFailure(e.getErrorCode());
    }

    // Validation 관련 (MethodArgumentNotValidException, BindException)
    @ExceptionHandler({MethodArgumentNotValidException.class, BindException.class})
    public ResponseEntity<ApiResponse<Void>> handleBindException(BindException e, HttpServletRequest request) {
        String detail = e.getBindingResult().getFieldErrors().stream()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .collect(Collectors.joining(", "));
        
        log.warn("[ValidationException] {} {} - Detail: {}", request.getMethod(), request.getRequestURI(), detail);
        
        return ApiResponse.onFailure(ErrorCode.INVALID_INPUT_VALUE, detail);
    }

    // 지원하지 않는 HTTP 메서드
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<ApiResponse<Void>> handleHttpRequestMethodNotSupportedException(HttpRequestMethodNotSupportedException e, HttpServletRequest request) {
        log.warn("[MethodNotSupported] {} {} - {}", request.getMethod(), request.getRequestURI(), e.getMessage());
        return ApiResponse.onFailure(ErrorCode.METHOD_NOT_ALLOWED);
    }

    // 기타 모든 예외 (500 Internal Server Error)
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleException(Exception e, HttpServletRequest request) {
        log.error("[InternalServerError] {} {} - ", request.getMethod(), request.getRequestURI(), e);
        return ApiResponse.onFailure(ErrorCode.INTERNAL_SERVER_ERROR);
    }
}
