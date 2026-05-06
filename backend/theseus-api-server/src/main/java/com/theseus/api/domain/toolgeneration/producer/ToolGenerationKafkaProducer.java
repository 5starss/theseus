package com.theseus.api.domain.toolgeneration.producer;

import com.theseus.api.common.kafka.KafkaTopicProperties;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;

@Slf4j
@RequiredArgsConstructor
@Component
public class ToolGenerationKafkaProducer {

	private final KafkaTemplate<String, Object> kafkaTemplate;
	private final KafkaTopicProperties kafkaTopicProperties;

	public void sendToolGenerationRequest(String key, Object event) {
		send(kafkaTopicProperties.toolGenerationRequest(), key, event);
	}

	public void sendToolRegenerationRequest(String key, Object event) {
		send(kafkaTopicProperties.toolRegenerationRequest(), key, event);
	}

	private void send(String topic, String key, Object event) {
		Objects.requireNonNull(event, "Kafka event must not be null");

		kafkaTemplate.send(topic, key, event)
			.whenComplete((result, exception) -> {
				if (exception != null) {
					log.warn(
						"Failed to send Kafka message. topic={}, key={}, eventType={}",
						topic,
						key,
						event.getClass().getSimpleName(),
						exception
					);
					return;
				}

				logSuccess(topic, key, result);
			});
	}

	private void logSuccess(String topic, String key, SendResult<String, Object> result) {
		if (result == null || result.getRecordMetadata() == null) {
			log.info("Sent Kafka message. topic={}, key={}", topic, key);
			return;
		}

		log.info(
			"Sent Kafka message. topic={}, key={}, partition={}, offset={}",
			topic,
			key,
			result.getRecordMetadata().partition(),
			result.getRecordMetadata().offset()
		);
	}
}
