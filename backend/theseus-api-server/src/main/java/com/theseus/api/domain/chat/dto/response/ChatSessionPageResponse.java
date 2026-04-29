package com.theseus.api.domain.chat.dto.response;

import java.util.List;
import lombok.Builder;
import lombok.Getter;
import org.springframework.data.domain.Page;

@Getter
@Builder
public class ChatSessionPageResponse<T> {

	private List<T> content;
	private int page;
	private int size;
	private long totalElements;
	private int totalPages;

	public static <T> ChatSessionPageResponse<T> createFrom(Page<T> page) {
		return ChatSessionPageResponse.<T>builder()
			.content(page.getContent())
			.page(page.getNumber())
			.size(page.getSize())
			.totalElements(page.getTotalElements())
			.totalPages(page.getTotalPages())
			.build();
	}
}
