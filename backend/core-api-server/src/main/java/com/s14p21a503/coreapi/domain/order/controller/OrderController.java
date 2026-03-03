package com.s14p21a503.coreapi.domain.order.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.order.dto.OrderRequestDto;
import com.s14p21a503.coreapi.domain.order.dto.OrderResponseDto;
import com.s14p21a503.coreapi.domain.order.service.OrderService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/orders")
public class OrderController {

    private final OrderService orderService;

    @PostMapping
    public ResponseEntity<ApiResponse<OrderResponseDto>> createOrder(
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody OrderRequestDto requestDto) {
        OrderResponseDto response = orderService.createOrder(userId, requestDto);
        return ApiResponse.onSuccess(SuccessCode.CREATED, response);
    }
}
