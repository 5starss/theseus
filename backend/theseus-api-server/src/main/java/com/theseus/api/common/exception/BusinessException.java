package com.theseus.api.common.exception;

import lombok.Getter;

@Getter
public class BusinessException extends RuntimeException {

	private final ErrorCode errorCode;

	protected BusinessException(ErrorCode errorCode) {
		super(errorCode.getMessage());
		this.errorCode = errorCode;
	}

	protected BusinessException(ErrorCode errorCode, String message) {
		super(message);
		this.errorCode = errorCode;
	}

	protected BusinessException(ErrorCode errorCode, Throwable cause) {
		super(errorCode.getMessage(), cause);
		this.errorCode = errorCode;
	}

	public static BusinessException of(ErrorCode errorCode) {
		return new BusinessException(errorCode);
	}

	public static BusinessException of(ErrorCode errorCode, Throwable cause) {
		return new BusinessException(errorCode, cause);
	}
}
