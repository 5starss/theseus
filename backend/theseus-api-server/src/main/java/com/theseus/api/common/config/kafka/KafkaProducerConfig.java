package com.theseus.api.common.config.kafka;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.util.Map;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.boot.autoconfigure.kafka.KafkaProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.serializer.JsonSerializer;

@Configuration
public class KafkaProducerConfig {

	@Bean
	public ProducerFactory<String, Object> producerFactory(
		KafkaProperties kafkaProperties,
		ObjectMapper objectMapper
	) {
		Map<String, Object> properties = kafkaProperties.buildProducerProperties();
		return new DefaultKafkaProducerFactory<>(
			properties,
			new StringSerializer(),
			new JsonSerializer<>(createKafkaObjectMapper(objectMapper))
		);
	}

	@Bean
	public KafkaTemplate<String, Object> kafkaTemplate(ProducerFactory<String, Object> producerFactory) {
		return new KafkaTemplate<>(producerFactory);
	}

	ObjectMapper createKafkaObjectMapper(ObjectMapper objectMapper) {
		return objectMapper.copy()
			.registerModule(new JavaTimeModule())
			.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
	}
}
