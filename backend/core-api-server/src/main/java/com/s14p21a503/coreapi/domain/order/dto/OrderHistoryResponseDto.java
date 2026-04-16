package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.common.response.PageResponseDto;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class OrderHistoryResponseDto {
    private PageResponseDto<PendingOrderDto> pending;
    private PageResponseDto<OrderHistoryDto> completed;
}
