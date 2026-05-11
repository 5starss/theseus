package com.theseus.api.domain.toolgeneration.redis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.theseus.api.domain.toolgeneration.config.ToolGenerationStateProperties;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

@ExtendWith(MockitoExtension.class)
class ToolPlanRunStateStoreTest {

	private static final String RUN_ID = "run-254";
	private static final String KEY = "tool:plan:run-254:state";

	@Mock
	private StringRedisTemplate stringRedisTemplate;

	@Mock
	private ValueOperations<String, String> valueOperations;

	private ObjectMapper objectMapper;
	private ToolPlanRunStateStore store;

	@BeforeEach
	void setUp() {
		objectMapper = new ObjectMapper()
			.registerModule(new JavaTimeModule())
			.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
		store = new ToolPlanRunStateStore(
			stringRedisTemplate,
			objectMapper,
			new ToolGenerationStateProperties(30, 1800000)
		);
		lenient().when(stringRedisTemplate.opsForValue()).thenReturn(valueOperations);
	}

	@Test
	@DisplayName("ToolPlanRun 상태 Redis key를 runId 기준으로 생성한다.")
	void buildKey() {
		assertThat(store.buildKey(RUN_ID)).isEqualTo(KEY);
	}

	@Test
	@DisplayName("ToolPlanRun 진행 상태를 TTL과 함께 저장한다.")
	void saveProgress() throws Exception {
		// Given
		ToolPlanRunState state = createState("progress");

		// When
		store.saveProgress(state);

		// Then
		verify(valueOperations).set(
			KEY,
			objectMapper.writeValueAsString(state),
			Duration.ofMinutes(30)
		);
	}

	@Test
	@DisplayName("runId로 최신 ToolPlanRun 상태를 조회한다.")
	void findByRunId() throws Exception {
		// Given
		ToolPlanRunState state = createState("completed");
		when(valueOperations.get(KEY)).thenReturn(objectMapper.writeValueAsString(state));

		// When
		Optional<ToolPlanRunState> found = store.findByRunId(RUN_ID);

		// Then
		assertThat(found).isPresent();
		assertThat(found.get().getRunId()).isEqualTo(RUN_ID);
		assertThat(found.get().getEventType()).isEqualTo("completed");
	}

	@Test
	@DisplayName("runId로 ToolPlanRun 상태를 삭제한다.")
	void deleteByRunId() {
		// When
		store.deleteByRunId(RUN_ID);

		// Then
		verify(stringRedisTemplate).delete(KEY);
	}

	@Test
	@DisplayName("Redis에 저장된 상태가 없으면 빈 Optional을 반환한다.")
	void findByRunIdWhenNotFound() {
		// Given
		when(valueOperations.get(anyString())).thenReturn(null);

		// When
		Optional<ToolPlanRunState> found = store.findByRunId(RUN_ID);

		// Then
		assertThat(found).isEmpty();
	}

	private ToolPlanRunState createState(String eventType) {
		return ToolPlanRunState.builder()
			.runId(RUN_ID)
			.projectId(1L)
			.chatSessionId(2L)
			.toolPlanGroupId(3L)
			.toolPlanId(4L)
			.planVersion(1L)
			.eventType(eventType)
			.status("GENERATING")
			.progressRate(50)
			.message("Generating plan.")
			.updatedAt(LocalDateTime.of(2026, 5, 11, 10, 0))
			.build();
	}
}
