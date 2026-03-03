package com.s14p21a503.coreapi.common.response.status;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum SuccessCode {

    OK(HttpStatus.OK, "GLOBAL-200", "요청 응답에 성공했습니다."),
    CREATED(HttpStatus.CREATED, "GLOBAL-201", "생성에 성공했습니다."),
    ;

    private final HttpStatus httpStatus;
    private final String code;
    private final String message;
    public boolean isSuccess() {
        return true;
    }
}
