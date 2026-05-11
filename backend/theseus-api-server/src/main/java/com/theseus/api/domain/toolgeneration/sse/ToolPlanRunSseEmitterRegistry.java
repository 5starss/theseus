package com.theseus.api.domain.toolgeneration.sse;

import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunSseEvent;
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
public class ToolPlanRunSseEmitterRegistry {

	private final Map<String, CopyOnWriteArrayList<SseEmitter>> emitters = new ConcurrentHashMap<>();

	public void register(Long projectId, Long chatSessionId, String runId, SseEmitter emitter) {
		String streamKey = createStreamKey(projectId, chatSessionId, runId);
		emitters.computeIfAbsent(streamKey, ignored -> new CopyOnWriteArrayList<>())
			.add(emitter);

		Runnable removeEmitter = () -> remove(projectId, chatSessionId, runId, emitter);
		emitter.onCompletion(removeEmitter);
		emitter.onTimeout(removeEmitter);
		emitter.onError(throwable -> removeEmitter.run());
	}

	public void sendToRun(Long projectId, Long chatSessionId, String runId, ToolPlanRunSseEvent event) {
		String streamKey = createStreamKey(projectId, chatSessionId, runId);
		List<SseEmitter> runEmitters = emitters.get(streamKey);
		if (runEmitters == null || runEmitters.isEmpty()) {
			return;
		}

		for (SseEmitter emitter : runEmitters) {
			sendToEmitter(projectId, chatSessionId, runId, emitter, event);
		}
	}

	public boolean sendToEmitter(
		Long projectId,
		Long chatSessionId,
		String runId,
		SseEmitter emitter,
		ToolPlanRunSseEvent event
	) {
		try {
			emitter.send(SseEmitter.event()
				.name(event.getEventType())
				.data(event));
			return true;
		} catch (IOException | IllegalStateException exception) {
			log.warn(
				">>>> ToolPlanRun SSE send failed. projectId={}, chatSessionId={}, runId={}, eventType={}",
				projectId,
				chatSessionId,
				runId,
				event.getEventType(),
				exception
			);
			remove(projectId, chatSessionId, runId, emitter);
			return false;
		}
	}

	public void remove(Long projectId, Long chatSessionId, String runId, SseEmitter emitter) {
		String streamKey = createStreamKey(projectId, chatSessionId, runId);
		List<SseEmitter> runEmitters = emitters.get(streamKey);
		if (runEmitters == null) {
			return;
		}

		runEmitters.remove(emitter);
		if (runEmitters.isEmpty()) {
			emitters.remove(streamKey);
		}
	}

	public void complete(Long projectId, Long chatSessionId, String runId) {
		String streamKey = createStreamKey(projectId, chatSessionId, runId);
		List<SseEmitter> runEmitters = emitters.remove(streamKey);
		if (runEmitters == null || runEmitters.isEmpty()) {
			return;
		}

		for (SseEmitter emitter : runEmitters) {
			try {
				emitter.complete();
			} catch (IllegalStateException exception) {
				log.debug(
					">>>> ToolPlanRun SSE emitter already completed. projectId={}, chatSessionId={}, runId={}",
					projectId,
					chatSessionId,
					runId
				);
			}
		}
	}

	int count(Long projectId, Long chatSessionId, String runId) {
		List<SseEmitter> runEmitters = emitters.get(createStreamKey(projectId, chatSessionId, runId));
		return runEmitters == null ? 0 : runEmitters.size();
	}

	private String createStreamKey(Long projectId, Long chatSessionId, String runId) {
		return projectId + ":" + chatSessionId + ":" + runId;
	}
}
