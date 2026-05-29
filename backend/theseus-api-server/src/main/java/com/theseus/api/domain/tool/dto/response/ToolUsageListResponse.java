package com.theseus.api.domain.tool.dto.response;

import java.util.List;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolUsageListResponse {

	private List<ToolUsageResponse> items;
	private int page;
	private int size;
	private long totalElements;
	private int totalPages;

	public static ToolUsageListResponse createFrom(
		List<ToolUsageResponse> items,
		int page,
		int size,
		long totalElements
	) {
		int totalPages = size <= 0 ? 0 : (int)Math.ceil((double)totalElements / size);

		return ToolUsageListResponse.builder()
			.items(items)
			.page(page)
			.size(size)
			.totalElements(totalElements)
			.totalPages(totalPages)
			.build();
	}
}
