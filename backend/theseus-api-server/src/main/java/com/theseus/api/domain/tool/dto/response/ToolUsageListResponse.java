package com.theseus.api.domain.tool.dto.response;

import java.util.List;
import lombok.Builder;
import lombok.Getter;
import org.springframework.data.domain.Page;

@Getter
@Builder
public class ToolUsageListResponse {

	private List<ToolUsageResponse> items;
	private int page;
	private int size;
	private long totalElements;
	private int totalPages;

	public static ToolUsageListResponse createFrom(Page<ToolUsageResponse> page) {
		return ToolUsageListResponse.builder()
			.items(page.getContent())
			.page(page.getNumber())
			.size(page.getSize())
			.totalElements(page.getTotalElements())
			.totalPages(page.getTotalPages())
			.build();
	}
}
