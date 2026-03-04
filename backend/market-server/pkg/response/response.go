package response

// ApiResponse 공통 JSON 응답 래퍼
type ApiResponse[T any] struct {
	IsSuccess bool   `json:"isSuccess"`
	Code      string `json:"code"`
	Message   string `json:"message"`
	Result    T      `json:"result"`
}

// OK 성공 응답을 반환한다.
func OK[T any](result T) ApiResponse[T] {
	return ApiResponse[T]{
		IsSuccess: true,
		Code:      "GLOBAL-200",
		Message:   "요청 응답에 성공했습니다.",
		Result:    result,
	}
}

// Fail 실패 응답을 반환한다.
func Fail(code, message string) ApiResponse[any] {
	return ApiResponse[any]{
		IsSuccess: false,
		Code:      code,
		Message:   message,
		Result:    nil,
	}
}
