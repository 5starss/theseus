package com.theseus.api.common.exception;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class GlobalExceptionHandlerTest {

	private final MockMvc mockMvc = MockMvcBuilders
		.standaloneSetup(new TestController())
		.setControllerAdvice(new GlobalExceptionHandler())
		.build();

	@Test
	@DisplayName("BusinessException 발생 시 code와 message만 실패 응답으로 반환한다")
	void handleBusinessException() throws Exception {
		// Given
		String path = "/business-exception";

		// When & Then
		mockMvc.perform(get(path))
			.andExpect(status().isUnauthorized())
			.andExpect(jsonPath("$.code").value(ErrorCode.LOGIN_FAILED.getCode()))
			.andExpect(jsonPath("$.message").value(ErrorCode.LOGIN_FAILED.getMessage()))
			.andExpect(jsonPath("$.isSuccess").doesNotExist())
			.andExpect(jsonPath("$.result").doesNotExist());
	}

	@Test
	@DisplayName("ResponseStatusException은 ErrorCode 기반 실패 응답으로 변환한다")
	void handleResponseStatusException() throws Exception {
		// Given
		String path = "/forbidden";

		// When & Then
		mockMvc.perform(get(path))
			.andExpect(status().isForbidden())
			.andExpect(jsonPath("$.code").value(ErrorCode.HANDLE_ACCESS_DENIED.getCode()))
			.andExpect(jsonPath("$.message").value(ErrorCode.HANDLE_ACCESS_DENIED.getMessage()))
			.andExpect(jsonPath("$.isSuccess").doesNotExist())
			.andExpect(jsonPath("$.result").doesNotExist());
	}

	@RestController
	private static class TestController {

		@GetMapping("/business-exception")
		void businessException() {
			throw BusinessException.of(ErrorCode.LOGIN_FAILED);
		}

		@GetMapping("/forbidden")
		void forbidden() {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN);
		}
	}
}
