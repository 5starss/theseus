package com.s14p21a503.coreapi.common.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import org.springframework.http.ResponseEntity;

public record ApiResponse<T>(
        Boolean isSuccess,
        String code,
        String message,
        @JsonInclude(JsonInclude.Include.NON_NULL)
        T result
) {

    // 성공 + 데이터
    public static <T> ResponseEntity<ApiResponse<T>> onSuccess(SuccessCode code, T result) {
        ApiResponse<T> body = new ApiResponse<>(
                code.isSuccess(),
                code.getCode(),
                code.getMessage(),
                result
        );
        return ResponseEntity.status(code.getHttpStatus()).body(body);
    }

    // 성공 + 데이터 없음
    public static ResponseEntity<ApiResponse<Void>> onSuccess(SuccessCode code) {
        ApiResponse<Void> body = new ApiResponse<>(
                code.isSuccess(),
                code.getCode(),
                code.getMessage(),
                null
        );
        return ResponseEntity.status(code.getHttpStatus()).body(body);
    }

    // 실패 + 기본 메시지
    public static ResponseEntity<ApiResponse<Void>> onFailure(ErrorCode code) {
        ApiResponse<Void> body = new ApiResponse<>(
                code.isSuccess(),   // 항상 false
                code.getCode(),
                code.getMessage(),
                null
        );
        return ResponseEntity.status(code.getHttpStatus()).body(body);
    }

    // 실패 + 커스텀 메시지
    public static ResponseEntity<ApiResponse<Void>> onFailure(ErrorCode code, String message) {
        ApiResponse<Void> body = new ApiResponse<>(
                code.isSuccess(),   // 항상 false
                code.getCode(),
                message,
                null
        );
        return ResponseEntity.status(code.getHttpStatus()).body(body);
    }

    // 실패 + 커스텀 메시지 + result
    public static <T> ResponseEntity<ApiResponse<T>> onFailure(ErrorCode code, String message, T result) {
        ApiResponse<T> body = new ApiResponse<>(
                code.isSuccess(),   // 항상 false
                code.getCode(),
                message,
                result
        );
        return ResponseEntity.status(code.getHttpStatus()).body(body);
    }
}