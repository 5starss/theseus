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
	@DisplayName("ResponseStatusException의 HTTP 상태와 메시지를 실패 응답에 반영한다")
	void handleResponseStatusExceptionWithReason() throws Exception {
		// Given
		String path = "/conflict";

		// When & Then
		mockMvc.perform(get(path))
			.andExpect(status().isConflict())
			.andExpect(jsonPath("$.isSuccess").value(false))
			.andExpect(jsonPath("$.code").value("HTTP-409"))
			.andExpect(jsonPath("$.message").value("종료된 채팅 세션에는 메시지를 등록할 수 없습니다."));
	}

	@Test
	@DisplayName("ResponseStatusException 메시지가 없으면 HTTP 기본 사유 문구를 사용한다")
	void handleResponseStatusExceptionWithoutReason() throws Exception {
		// Given
		String path = "/forbidden";

		// When & Then
		mockMvc.perform(get(path))
			.andExpect(status().isForbidden())
			.andExpect(jsonPath("$.isSuccess").value(false))
			.andExpect(jsonPath("$.code").value("HTTP-403"))
			.andExpect(jsonPath("$.message").value("Forbidden"));
	}

	@RestController
	private static class TestController {

		@GetMapping("/conflict")
		void conflict() {
			throw new ResponseStatusException(
				HttpStatus.CONFLICT,
				"종료된 채팅 세션에는 메시지를 등록할 수 없습니다."
			);
		}

		@GetMapping("/forbidden")
		void forbidden() {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN);
		}
	}
}
