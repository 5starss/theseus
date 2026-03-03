package com.s14p21a503.coreapi.common.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.s14p21a503.coreapi.common.exception.ErrorCode;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import org.springframework.http.HttpStatus;

/**
 * API 응답 형식을 통일하기 위한 공통 응답 DTO 클래스입니다.
 *
 * @param <T> 응답 데이터의 타입
 */
@Getter
@Schema(description = "API 공통 응답 포맷")
public class RestApiResponse<T> {

    @Schema(description = "성공 여부", example = "true")
    private final boolean success;

    @Schema(description = "HTTP 상태 코드", example = "200")
    private final int code;

    @Schema(description = "응답 메시지", example = "요청에 성공하였습니다.")
    private final String message;

    @Schema(description = "응답 데이터 (성공 시)")
    @JsonInclude(JsonInclude.Include.NON_NULL)
    private final T data;

    @Schema(description = "에러 코드 (실패 시)", example = "USER_NOT_FOUND")
    @JsonInclude(JsonInclude.Include.NON_NULL)
    private final String errorCode;

    @Builder(access = AccessLevel.PRIVATE)
    private RestApiResponse(boolean success, int code, String message, T data, String errorCode) {
        this.success = success;
        this.code = code;
        this.message = message;
        this.data = data;
        this.errorCode = errorCode;
    }

    // --- 성공 응답 팩토리 메서드 ---
    public static <T> RestApiResponse<T> success(HttpStatus status, String message, T data) {
        return RestApiResponse.<T>builder()
                .success(true)
                .code(status.value())
                .message(message)
                .data(data)
                .build();
    }

    public static <T> RestApiResponse<T> success(T data) {
        return success(HttpStatus.OK, "요청에 성공했습니다.", data);
    }

    public static <T> RestApiResponse<T> created(T data) {
        return success(HttpStatus.CREATED, "생성되었습니다.", data);
    }

    // --- 실패 응답 팩토리 메서드 ---
    public static <T> RestApiResponse<T> fail(ErrorCode errorCode) { // ErrorCode는 프로젝트의 Enum 클래스
        return RestApiResponse.<T>builder()
                .success(false)
                .code(errorCode.getHttpStatus().value())
                .message(errorCode.getMessage())
                .errorCode(errorCode.getCode())
                .build();
    }

    // 상세 메시지를 오버라이딩 해야 할 때
    public static <T> RestApiResponse<T> fail(ErrorCode errorCode, String customMessage) {
        return RestApiResponse.<T>builder()
                .success(false)
                .code(errorCode.getHttpStatus().value())
                .message(customMessage)
                .errorCode(errorCode.getCode())
                .build();
    }
}