package com.s14p21a503.coreapi.common.exception;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

/**
 * 애플리케이션 전역에서 사용되는 에러 코드와 메시지, HTTP 상태 코드를 정의하는 열거형 클래스입니다.
 *
 * @summary 전역 에러 코드 정의
 */
@Getter
@RequiredArgsConstructor
public enum ErrorCode {

    INVALID_INPUT_VALUE(HttpStatus.BAD_REQUEST, "COMMON001", "잘못된 입력값입니다."),
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "COMMON002", "서버 내부 에러가 발생했습니다."),
    ENTITY_NOT_FOUND(HttpStatus.NOT_FOUND, "COMMON003", "존재하지 않는 리소스입니다."),
    METHOD_NOT_ALLOWED(HttpStatus.METHOD_NOT_ALLOWED, "COMMON004", "지원하지 않는 HTTP 메서드입니다."),
    DUPLICATE_RESOURCE(HttpStatus.CONFLICT, "COMMON005", "이미 존재하는 리소스입니다."),

    ACCESS_DENIED(HttpStatus.FORBIDDEN, "AUTH-008", "해당 기능에 접근할 권한이 없습니다."),
    INVALID_TOKEN(HttpStatus.UNAUTHORIZED, "AUTH001", "유효하지 않은 토큰입니다."),
    DUPLICATE_EMAIL(HttpStatus.CONFLICT, "AUTH002", "이미 가입된 이메일입니다."),
    INVALID_VERIFICATION_CODE(HttpStatus.BAD_REQUEST, "AUTH003", "인증 코드가 올바르지 않거나 만료되었습니다."),
    EMAIL_NOT_VERIFIED(HttpStatus.UNAUTHORIZED, "AUTH004", "이메일 인증이 완료되지 않았습니다."),
    LOGIN_FAILED(HttpStatus.UNAUTHORIZED, "AUTH005", "이메일 또는 비밀번호가 일치하지 않습니다."),
    EMAIL_SEND_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "AUTH006", "이메일 발송에 실패했습니다."),
    INVALID_REFRESH_TOKEN(HttpStatus.UNAUTHORIZED, "AUTH007", "유효하지 않은 리프레시 토큰입니다."),

    // --- 주문 / 계좌 / 포지션 관련 에러 코드 ---
    ACCOUNT_NOT_FOUND(HttpStatus.NOT_FOUND, "ACC001", "해당 유저의 계좌 정보를 찾을 수 없습니다."),
    POSITION_NOT_FOUND(HttpStatus.BAD_REQUEST, "POS001", "해당 종목의 보유 주식이 없습니다."),
    INSUFFICIENT_BALANCE(HttpStatus.BAD_REQUEST, "ORD001", "주문 가능한 잔고가 부족합니다."),
    INSUFFICIENT_QUANTITY(HttpStatus.BAD_REQUEST, "ORD002", "주문 가능한 보유 주식이 부족합니다.");

    private final HttpStatus httpStatus;
    private final String code;
    private final String message;
}
