package com.theseus.api.common.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.common.response.status.SuccessCode;
import org.springframework.http.ResponseEntity;

public record ApiResponse<T>(
        Boolean isSuccess,
        String code,
        String message,
        @JsonInclude(JsonInclude.Include.NON_NULL) T result) {
    // 성공 응답 (데이터 포함)
    public static <T> ResponseEntity<ApiResponse<T>> onSuccess(SuccessCode code, T result) {
        ApiResponse<T> body = new ApiResponse<>(
                true,
                code.getCode(),
                code.getMessage(),
                result);
        return ResponseEntity.status(code.getHttpStatus()).body(body);
    }

    // 성공 응답 (데이터 미포함)
    public static ResponseEntity<ApiResponse<Void>> onSuccess(SuccessCode code) {
        ApiResponse<Void> body = new ApiResponse<>(
                true,
                code.getCode(),
                code.getMessage(),
                null);
        return ResponseEntity.status(code.getHttpStatus()).body(body);
    }

    // 실패 응답 (ErrorCode 기반)
    public static ResponseEntity<ApiResponse<Void>> onFailure(ErrorCode code) {
        ApiResponse<Void> body = new ApiResponse<>(
                false,
                code.getCode(),
                code.getMessage(),
                null);
        return ResponseEntity.status(code.getStatus()).body(body);
    }

    // 실패 응답 (메시지 커스텀)
    public static ResponseEntity<ApiResponse<Void>> onFailure(ErrorCode code, String message) {
        ApiResponse<Void> body = new ApiResponse<>(
                false,
                code.getCode(),
                message,
                null);
        return ResponseEntity.status(code.getStatus()).body(body);
    }
}
