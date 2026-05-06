package com.theseus.api.common.response.status;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum SuccessCode {

    // Common
    OK(HttpStatus.OK, "COMMON-200", "성공입니다."),
    CREATED(HttpStatus.CREATED, "COMMON-201", "리소스가 생성되었습니다."),
    ACCEPTED(HttpStatus.ACCEPTED, "COMMON-202", "요청 처리를 시작했습니다.");

    private final HttpStatus httpStatus;
    private final String code;
    private final String message;

    public boolean isSuccess() {
        return true;
    }
}
