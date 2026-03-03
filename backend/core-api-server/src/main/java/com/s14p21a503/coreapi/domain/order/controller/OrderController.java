package com.s14p21a503.coreapi.domain.order.controller;

import com.s14p21a503.coreapi.domain.order.dto.OrderRequestDto;
import com.s14p21a503.coreapi.domain.order.dto.OrderResponseDto;
import com.s14p21a503.coreapi.domain.order.service.OrderService;
import com.s14p21a503.coreapi.common.response.RestApiResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping
    public ResponseEntity<RestApiResponse<OrderResponseDto>> createOrder(
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody OrderRequestDto requestDto) {
        OrderResponseDto response = orderService.createOrder(userId, requestDto);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(RestApiResponse.success(HttpStatus.CREATED, "주문 생성을 성공했습니다.", response));
    }
}
