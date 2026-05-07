package com.theseus.api.domain.toolgeneration.redis;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.domain.toolgeneration.config.ToolGenerationStateProperties;
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationState;
import java.time.LocalDateTime;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@RequiredArgsConstructor
@Component
public class ToolGenerationStateStore {

	private static final String KEY_PREFIX = "tool:generation:";
	private static final String KEY_SUFFIX = ":state";

	private final StringRedisTemplate stringRedisTemplate;
	private final ObjectMapper objectMapper;
	private final ToolGenerationStateProperties properties;

	public void saveProgress(ToolGenerationState state) {
		save(state);
	}

	public void saveChunk(ToolGenerationState state) {
		save(state);
	}

	public void saveCompleted(ToolGenerationState state) {
		save(state);
	}

	public void saveFailed(ToolGenerationState state) {
		save(state);
	}

	public Optional<ToolGenerationState> findByToolId(Long toolId) {
		String json = stringRedisTemplate.opsForValue().get(buildKey(toolId));
		if (json == null || json.isBlank()) {
			return Optional.empty();
		}

		try {
			return Optional.of(objectMapper.readValue(json, ToolGenerationState.class));
		} catch (JsonProcessingException exception) {
			throw new IllegalStateException("Failed to deserialize tool generation state.", exception);
		}
	}

	public void deleteByToolId(Long toolId) {
		stringRedisTemplate.delete(buildKey(toolId));
	}

	String buildKey(Long toolId) {
		if (toolId == null) {
			throw new IllegalArgumentException("toolId must not be null.");
		}
		return KEY_PREFIX + toolId + KEY_SUFFIX;
	}

	private void save(ToolGenerationState state) {
		ToolGenerationState stateToSave = requireState(state);
		try {
			stringRedisTemplate.opsForValue()
				.set(
					buildKey(stateToSave.getToolId()),
					objectMapper.writeValueAsString(stateToSave),
					properties.stateTtl()
				);
		} catch (JsonProcessingException exception) {
			throw new IllegalStateException("Failed to serialize tool generation state.", exception);
		}
	}

	private ToolGenerationState requireState(ToolGenerationState state) {
		if (state == null) {
			throw new IllegalArgumentException("state must not be null.");
		}
		if (state.getToolId() == null) {
			throw new IllegalArgumentException("state.toolId must not be null.");
		}
		if (state.getUpdatedAt() != null) {
			return state;
		}
		return state.toBuilder()
			.updatedAt(LocalDateTime.now())
			.build();
	}
}
