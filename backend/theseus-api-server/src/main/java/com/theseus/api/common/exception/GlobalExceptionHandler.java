package com.theseus.api.common.exception;

import jakarta.servlet.http.HttpServletRequest;
import java.util.stream.Collectors;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.access.AccessDeniedException;
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

	@ExceptionHandler(BusinessException.class)
	public ResponseEntity<ErrorResponse> handleBusinessException(BusinessException e, HttpServletRequest request) {
		log.warn("[BusinessException] {} {} - Code: {}, Message: {}",
			request.getMethod(), request.getRequestURI(), e.getErrorCode().getCode(), e.getMessage());
		return ResponseEntity.status(e.getErrorCode().getStatus())
			.body(ErrorResponse.from(e.getErrorCode()));
	}

	@ExceptionHandler({MethodArgumentNotValidException.class, BindException.class})
	public ResponseEntity<ErrorResponse> handleBindException(BindException e, HttpServletRequest request) {
		String detail = e.getBindingResult().getFieldErrors().stream()
			.map(error -> error.getField() + ": " + error.getDefaultMessage())
			.collect(Collectors.joining(", "));

		log.warn("[ValidationException] {} {} - Detail: {}", request.getMethod(), request.getRequestURI(), detail);

		return ResponseEntity.status(ErrorCode.INVALID_INPUT_VALUE.getStatus())
			.body(ErrorResponse.from(ErrorCode.INVALID_INPUT_VALUE));
	}

	@ExceptionHandler(HttpRequestMethodNotSupportedException.class)
	public ResponseEntity<ErrorResponse> handleHttpRequestMethodNotSupportedException(
		HttpRequestMethodNotSupportedException e,
		HttpServletRequest request
	) {
		log.warn("[MethodNotSupported] {} {} - {}", request.getMethod(), request.getRequestURI(), e.getMessage());
		return ResponseEntity.status(ErrorCode.METHOD_NOT_ALLOWED.getStatus())
			.body(ErrorResponse.from(ErrorCode.METHOD_NOT_ALLOWED));
	}

	@ExceptionHandler(AccessDeniedException.class)
	public ResponseEntity<ErrorResponse> handleAccessDeniedException(
		AccessDeniedException e,
		HttpServletRequest request
	) {
		log.warn("[AccessDeniedException] {} {} - {}", request.getMethod(), request.getRequestURI(), e.getMessage());
		return ResponseEntity.status(ErrorCode.HANDLE_ACCESS_DENIED.getStatus())
			.body(ErrorResponse.from(ErrorCode.HANDLE_ACCESS_DENIED));
	}

	@ExceptionHandler(ResponseStatusException.class)
	public ResponseEntity<ErrorResponse> handleResponseStatusException(
		ResponseStatusException e,
		HttpServletRequest request
	) {
		ErrorCode errorCode = resolveResponseStatusErrorCode(e.getStatusCode());

		log.warn("[ResponseStatusException] {} {} - Code: {}, Message: {}",
			request.getMethod(), request.getRequestURI(), errorCode.getCode(), getResponseStatusMessage(e));

		return ResponseEntity.status(errorCode.getStatus())
			.body(ErrorResponse.from(errorCode));
	}

	private ErrorCode resolveResponseStatusErrorCode(HttpStatusCode statusCode) {
		if (statusCode.isSameCodeAs(HttpStatus.BAD_REQUEST)) {
			return ErrorCode.INVALID_INPUT_VALUE;
		}
		if (statusCode.isSameCodeAs(HttpStatus.UNAUTHORIZED)) {
			return ErrorCode.UNAUTHORIZED;
		}
		if (statusCode.isSameCodeAs(HttpStatus.FORBIDDEN)) {
			return ErrorCode.HANDLE_ACCESS_DENIED;
		}
		if (statusCode.isSameCodeAs(HttpStatus.METHOD_NOT_ALLOWED)) {
			return ErrorCode.METHOD_NOT_ALLOWED;
		}
		return ErrorCode.INTERNAL_SERVER_ERROR;
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
	public ResponseEntity<ErrorResponse> handleException(Exception e, HttpServletRequest request) {
		log.error("[InternalServerError] {} {} - ", request.getMethod(), request.getRequestURI(), e);
		return ResponseEntity.status(ErrorCode.INTERNAL_SERVER_ERROR.getStatus())
			.body(ErrorResponse.from(ErrorCode.INTERNAL_SERVER_ERROR));
	}
}
