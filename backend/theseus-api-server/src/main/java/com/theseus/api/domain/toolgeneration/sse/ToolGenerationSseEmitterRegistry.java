package com.theseus.api.domain.toolgeneration.sse;

import com.theseus.api.domain.toolgeneration.dto.ToolGenerationSseEvent;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@Slf4j
@Component
public class ToolGenerationSseEmitterRegistry {

	private final Map<String, CopyOnWriteArrayList<SseEmitter>> emitters = new ConcurrentHashMap<>();

	public void register(Long projectId, Long chatSessionId, Long toolId, SseEmitter emitter) {
		String streamKey = createStreamKey(projectId, chatSessionId, toolId);
		emitters.computeIfAbsent(streamKey, ignored -> new CopyOnWriteArrayList<>())
			.add(emitter);

		Runnable removeEmitter = () -> remove(projectId, chatSessionId, toolId, emitter);
		emitter.onCompletion(removeEmitter);
		emitter.onTimeout(removeEmitter);
		emitter.onError(throwable -> removeEmitter.run());
	}

	public void sendToTool(Long projectId, Long chatSessionId, Long toolId, ToolGenerationSseEvent event) {
		String streamKey = createStreamKey(projectId, chatSessionId, toolId);
		List<SseEmitter> toolEmitters = emitters.get(streamKey);
		if (toolEmitters == null || toolEmitters.isEmpty()) {
			return;
		}

		for (SseEmitter emitter : toolEmitters) {
			sendToEmitter(projectId, chatSessionId, toolId, emitter, event);
		}
	}

	public boolean sendToEmitter(
		Long projectId,
		Long chatSessionId,
		Long toolId,
		SseEmitter emitter,
		ToolGenerationSseEvent event
	) {
		try {
			emitter.send(SseEmitter.event()
				.name(event.getEventType())
				.data(event));
			return true;
		} catch (IOException | IllegalStateException exception) {
			log.warn(
				">>>> Tool generation SSE send failed. projectId={}, chatSessionId={}, toolId={}, eventType={}",
				projectId,
				chatSessionId,
				toolId,
				event.getEventType(),
				exception
			);
			remove(projectId, chatSessionId, toolId, emitter);
			return false;
		}
	}

	public void remove(Long projectId, Long chatSessionId, Long toolId, SseEmitter emitter) {
		String streamKey = createStreamKey(projectId, chatSessionId, toolId);
		List<SseEmitter> toolEmitters = emitters.get(streamKey);
		if (toolEmitters == null) {
			return;
		}

		toolEmitters.remove(emitter);
		if (toolEmitters.isEmpty()) {
			emitters.remove(streamKey);
		}
	}

	public void complete(Long projectId, Long chatSessionId, Long toolId) {
		String streamKey = createStreamKey(projectId, chatSessionId, toolId);
		List<SseEmitter> toolEmitters = emitters.remove(streamKey);
		if (toolEmitters == null || toolEmitters.isEmpty()) {
			return;
		}

		for (SseEmitter emitter : toolEmitters) {
			try {
				emitter.complete();
			} catch (IllegalStateException exception) {
				log.debug(
					">>>> Tool generation SSE emitter already completed. projectId={}, chatSessionId={}, toolId={}",
					projectId,
					chatSessionId,
					toolId
				);
			}
		}
	}

	int count(Long projectId, Long chatSessionId, Long toolId) {
		List<SseEmitter> toolEmitters = emitters.get(createStreamKey(projectId, chatSessionId, toolId));
		return toolEmitters == null ? 0 : toolEmitters.size();
	}

	private String createStreamKey(Long projectId, Long chatSessionId, Long toolId) {
		return projectId + ":" + chatSessionId + ":" + toolId;
	}
}
