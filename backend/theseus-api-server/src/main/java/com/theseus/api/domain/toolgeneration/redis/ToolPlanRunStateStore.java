package com.theseus.api.domain.toolgeneration.redis;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.domain.toolgeneration.config.ToolGenerationStateProperties;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import java.time.LocalDateTime;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@RequiredArgsConstructor
@Component
public class ToolPlanRunStateStore {

	private static final String KEY_PREFIX = "tool:plan:";
	private static final String KEY_SUFFIX = ":state";

	private final StringRedisTemplate stringRedisTemplate;
	private final ObjectMapper objectMapper;
	private final ToolGenerationStateProperties properties;

	public void saveProgress(ToolPlanRunState state) {
		ToolPlanRunState mergedState = findByRunId(state.getRunId())
			.map(existing -> state.toBuilder()
				.content(existing.getContent()) // Preserve existing content
				.build())
			.orElse(state);
		save(mergedState);
	}

	public void saveChunk(ToolPlanRunState state) {
		ToolPlanRunState mergedState = findByRunId(state.getRunId())
			.map(existing -> {
				String accumulatedContent = (existing.getContent() == null ? "" : existing.getContent())
					+ (state.getContent() == null ? "" : state.getContent());
				return state.toBuilder()
					.content(accumulatedContent)
					.build();
			})
			.orElse(state);
		save(mergedState);
	}

	public void saveCompleted(ToolPlanRunState state) {
		save(state);
	}

	public void saveSkipped(ToolPlanRunState state) {
		save(state);
	}

	public void saveFailed(ToolPlanRunState state) {
		save(state);
	}

	public Optional<ToolPlanRunState> findByRunId(String runId) {
		String json = stringRedisTemplate.opsForValue().get(buildKey(runId));
		if (json == null || json.isBlank()) {
			return Optional.empty();
		}

		try {
			return Optional.of(objectMapper.readValue(json, ToolPlanRunState.class));
		} catch (JsonProcessingException exception) {
			throw new IllegalStateException("Failed to deserialize ToolPlanRun state.", exception);
		}
	}

	public void deleteByRunId(String runId) {
		stringRedisTemplate.delete(buildKey(runId));
	}

	String buildKey(String runId) {
		if (runId == null || runId.isBlank()) {
			throw new IllegalArgumentException("runId must not be blank.");
		}
		return KEY_PREFIX + runId + KEY_SUFFIX;
	}

	private void save(ToolPlanRunState state) {
		ToolPlanRunState stateToSave = requireState(state);
		try {
			stringRedisTemplate.opsForValue()
				.set(
					buildKey(stateToSave.getRunId()),
					objectMapper.writeValueAsString(stateToSave),
					properties.stateTtl()
				);
		} catch (JsonProcessingException exception) {
			throw new IllegalStateException("Failed to serialize ToolPlanRun state.", exception);
		}
	}

	private ToolPlanRunState requireState(ToolPlanRunState state) {
		if (state == null) {
			throw new IllegalArgumentException("state must not be null.");
		}
		if (state.getRunId() == null || state.getRunId().isBlank()) {
			throw new IllegalArgumentException("state.runId must not be blank.");
		}
		if (state.getUpdatedAt() != null) {
			return state;
		}
		return state.toBuilder()
			.updatedAt(LocalDateTime.now())
			.build();
	}
}
