package com.theseus.api.domain.toolgeneration.config;

import com.theseus.api.domain.toolgeneration.event.ToolPlanEvent;
import java.util.HashMap;
import java.util.Map;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.support.serializer.JsonDeserializer;

@Configuration
public class ToolPlanKafkaConsumerConfig {

	@Bean
	public ConcurrentKafkaListenerContainerFactory<String, ToolPlanEvent> toolPlanKafkaListenerContainerFactory(
		@Value("${spring.kafka.bootstrap-servers}") String bootstrapServers,
		@Value("${spring.kafka.consumer.group-id}") String groupId,
		@Value("${spring.kafka.consumer.auto-offset-reset:earliest}") String autoOffsetReset
	) {
		Map<String, Object> properties = new HashMap<>();
		properties.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
		properties.put(ConsumerConfig.GROUP_ID_CONFIG, groupId);
		properties.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
		properties.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, JsonDeserializer.class);
		properties.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, autoOffsetReset);
		properties.put(JsonDeserializer.TRUSTED_PACKAGES, "com.theseus.api.domain.toolgeneration.event,java.util,java.lang,com.fasterxml.jackson.databind");
		properties.put(JsonDeserializer.VALUE_DEFAULT_TYPE, ToolPlanEvent.class.getName());
		properties.put(JsonDeserializer.USE_TYPE_INFO_HEADERS, false);

		DefaultKafkaConsumerFactory<String, ToolPlanEvent> consumerFactory = new DefaultKafkaConsumerFactory<>(properties);
		ConcurrentKafkaListenerContainerFactory<String, ToolPlanEvent> factory =
			new ConcurrentKafkaListenerContainerFactory<>();
		factory.setConsumerFactory(consumerFactory);
		return factory;
	}
}
