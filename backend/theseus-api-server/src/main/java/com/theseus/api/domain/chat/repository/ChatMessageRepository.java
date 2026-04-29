package com.theseus.api.domain.chat.repository;

import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.tool.entity.Tool;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {

	List<ChatMessage> findByChatSessionOrderByMessageOrderAsc(ChatSession chatSession);

	List<ChatMessage> findByChatSessionAndToolOrderByMessageOrderAsc(ChatSession chatSession, Tool tool);

	List<ChatMessage> findByToolOrderByMessageOrderAsc(Tool tool);

	Optional<ChatMessage> findByChatSessionAndMessageOrder(ChatSession chatSession, Integer messageOrder);

	Optional<ChatMessage> findTopByChatSessionOrderByMessageOrderDesc(ChatSession chatSession);

	Optional<ChatMessage> findTopByChatSessionAndToolOrderByMessageOrderDesc(ChatSession chatSession, Tool tool);
}
