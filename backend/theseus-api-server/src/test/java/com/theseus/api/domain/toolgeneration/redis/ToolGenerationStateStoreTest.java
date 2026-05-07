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
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationState;
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
class ToolGenerationStateStoreTest {

	private static final Long TOOL_ID = 40L;
	private static final String KEY = "tool:generation:40:state";

	@Mock
	private StringRedisTemplate stringRedisTemplate;

	@Mock
	private ValueOperations<String, String> valueOperations;

	private ObjectMapper objectMapper;
	private ToolGenerationStateStore store;

	@BeforeEach
	void setUp() {
		objectMapper = new ObjectMapper()
			.registerModule(new JavaTimeModule())
			.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
		store = new ToolGenerationStateStore(
			stringRedisTemplate,
			objectMapper,
			new ToolGenerationStateProperties(30, 1800000)
		);
		lenient().when(stringRedisTemplate.opsForValue()).thenReturn(valueOperations);
	}

	@Test
	@DisplayName("Tool 생성 상태 Redis key를 생성한다.")
	void buildKey() {
		assertThat(store.buildKey(TOOL_ID)).isEqualTo(KEY);
	}

	@Test
	@DisplayName("Tool 생성 상태를 JSON으로 직렬화하고 역직렬화한다.")
	void serializeAndDeserializeState() throws Exception {
		ToolGenerationState state = createState();

		String json = objectMapper.writeValueAsString(state);
		ToolGenerationState restored = objectMapper.readValue(json, ToolGenerationState.class);

		assertThat(restored.getToolId()).isEqualTo(TOOL_ID);
		assertThat(restored.getEventType()).isEqualTo("PROGRESS");
		assertThat(restored.getUpdatedAt()).isEqualTo(LocalDateTime.of(2026, 5, 7, 10, 0));
	}

	@Test
	@DisplayName("Tool 생성 진행 상태를 TTL과 함께 저장한다.")
	void saveProgress() throws Exception {
		ToolGenerationState state = createState();

		store.saveProgress(state);

		verify(valueOperations).set(
			KEY,
			objectMapper.writeValueAsString(state),
			Duration.ofMinutes(30)
		);
	}

	@Test
	@DisplayName("Tool ID로 최신 생성 상태를 조회한다.")
	void findByToolId() throws Exception {
		ToolGenerationState state = createState();
		when(valueOperations.get(KEY)).thenReturn(objectMapper.writeValueAsString(state));

		Optional<ToolGenerationState> found = store.findByToolId(TOOL_ID);

		assertThat(found).isPresent();
		assertThat(found.get().getToolId()).isEqualTo(TOOL_ID);
		assertThat(found.get().getProgressRate()).isEqualTo(50);
	}

	@Test
	@DisplayName("Tool ID로 생성 상태를 삭제한다.")
	void deleteByToolId() {
		store.deleteByToolId(TOOL_ID);

		verify(stringRedisTemplate).delete(KEY);
	}

	@Test
	@DisplayName("Redis에 저장된 상태가 없으면 빈 Optional을 반환한다.")
	void findByToolIdWhenNotFound() {
		when(valueOperations.get(anyString())).thenReturn(null);

		Optional<ToolGenerationState> found = store.findByToolId(TOOL_ID);

		assertThat(found).isEmpty();
	}

	private ToolGenerationState createState() {
		return ToolGenerationState.builder()
			.projectId(20L)
			.chatSessionId(30L)
			.toolId(TOOL_ID)
			.eventType("PROGRESS")
			.status("GENERATING")
			.draftPhase("PLAN")
			.progressRate(50)
			.message("Generating tool draft.")
			.content("chunk")
			.draftVersion(1)
			.updatedAt(LocalDateTime.of(2026, 5, 7, 10, 0))
			.build();
	}
}
