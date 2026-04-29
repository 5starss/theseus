package com.theseus.api.common.exception;

import com.theseus.api.common.response.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import java.util.stream.Collectors;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

	@ExceptionHandler(CustomException.class)
	public ResponseEntity<ApiResponse<Void>> handleCustomException(CustomException e, HttpServletRequest request) {
		log.warn("[CustomException] {} {} - Code: {}, Message: {}",
			request.getMethod(), request.getRequestURI(), e.getErrorCode().getCode(), e.getMessage());
		return ApiResponse.onFailure(e.getErrorCode());
	}

	@ExceptionHandler({MethodArgumentNotValidException.class, BindException.class})
	public ResponseEntity<ApiResponse<Void>> handleBindException(BindException e, HttpServletRequest request) {
		String detail = e.getBindingResult().getFieldErrors().stream()
			.map(error -> error.getField() + ": " + error.getDefaultMessage())
			.collect(Collectors.joining(", "));

		log.warn("[ValidationException] {} {} - Detail: {}", request.getMethod(), request.getRequestURI(), detail);

		return ApiResponse.onFailure(ErrorCode.INVALID_INPUT_VALUE, detail);
	}

	@ExceptionHandler(HttpRequestMethodNotSupportedException.class)
	public ResponseEntity<ApiResponse<Void>> handleHttpRequestMethodNotSupportedException(
		HttpRequestMethodNotSupportedException e,
		HttpServletRequest request
	) {
		log.warn("[MethodNotSupported] {} {} - {}", request.getMethod(), request.getRequestURI(), e.getMessage());
		return ApiResponse.onFailure(ErrorCode.METHOD_NOT_ALLOWED);
	}

	@ExceptionHandler(ResponseStatusException.class)
	public ResponseEntity<ApiResponse<Void>> handleResponseStatusException(
		ResponseStatusException e,
		HttpServletRequest request
	) {
		HttpStatusCode statusCode = e.getStatusCode();
		String code = "HTTP-" + statusCode.value();
		String message = getResponseStatusMessage(e);

		log.warn("[ResponseStatusException] {} {} - Code: {}, Message: {}",
			request.getMethod(), request.getRequestURI(), code, message);

		return ApiResponse.onFailure(statusCode, code, message);
	}

	private String getResponseStatusMessage(ResponseStatusException e) {
		if (e.getReason() != null && !e.getReason().isBlank()) {
			return e.getReason();
		}

		HttpStatus httpStatus = HttpStatus.resolve(e.getStatusCode().value());
		if (httpStatus != null) {
			return httpStatus.getReasonPhrase();
		}

		return e.getStatusCode().toString();
	}

	@ExceptionHandler(Exception.class)
	public ResponseEntity<ApiResponse<Void>> handleException(Exception e, HttpServletRequest request) {
		log.error("[InternalServerError] {} {} - ", request.getMethod(), request.getRequestURI(), e);
		return ApiResponse.onFailure(ErrorCode.INTERNAL_SERVER_ERROR);
	}
}
