package com.s14p21a503.coreapi.domain.order.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.order.dto.OrderHistoryResponseDto;
import com.s14p21a503.coreapi.domain.order.dto.OrderRequestDto;
import com.s14p21a503.coreapi.domain.order.dto.OrderResponseDto;
import com.s14p21a503.coreapi.domain.order.dto.OrderHistoryDetailResponseDto;
import com.s14p21a503.coreapi.domain.order.dto.OrderDetailResponseDto;
import com.s14p21a503.coreapi.domain.order.service.OrderService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;

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

    @PostMapping("/{orderId}/cancel")
    public ResponseEntity<ApiResponse<Void>> cancelOrder(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long orderId) {
        orderService.cancelOrder(userId, orderId);
        return ApiResponse.onSuccess(SuccessCode.ACCEPTED, null);
    }

    @GetMapping
    public ResponseEntity<ApiResponse<OrderHistoryResponseDto>> getOrders(
            @RequestHeader("X-User-Id") Long userId,
            @RequestParam(value = "account_type", defaultValue = "USER") AccountType accountType,
            @RequestParam(value = "page", defaultValue = "0") int page,
            @RequestParam(value = "size", defaultValue = "20") int size,
            @RequestParam(value = "status", required = false) String status,
            @RequestParam(value = "ticker", required = false) String ticker,
            @RequestParam(value = "yearMonth", required = false) String yearMonth
    ) {
        String filter = (status != null && !status.isEmpty()) ? status.toUpperCase() : "ALL";

        LocalDateTime startDate = null;
        LocalDateTime endDate = null;
        if (yearMonth != null && yearMonth.matches("\\d{4}-\\d{2}")) {
            try {
                LocalDate startLocalDate = LocalDate.parse(yearMonth + "-01", DateTimeFormatter.ofPattern("yyyy-MM-dd"));
                startDate = startLocalDate.atStartOfDay();
                endDate = startDate.plusMonths(1);
            } catch (DateTimeParseException e) {
                // 형식이 맞지 않으면 기간 필터를 무시합니다.
            }
        }

        String parsedTicker = (ticker != null && ticker.trim().isEmpty()) ? null : ticker;
        Pageable pageable = PageRequest.of(page, size);

        OrderHistoryResponseDto response = 
            orderService.getOrders(userId, accountType, filter, parsedTicker, startDate, endDate, pageable);
        
        return ApiResponse.onSuccess(SuccessCode.OK, response);
    }

    @GetMapping("/completed/{historyId}")
    public ResponseEntity<ApiResponse<OrderHistoryDetailResponseDto>> getHistoryDetail(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long historyId) {

        OrderHistoryDetailResponseDto response = orderService.getHistoryDetail(userId, historyId);
        return ApiResponse.onSuccess(SuccessCode.OK, response);
    }

    @GetMapping("/pending/{orderId}")
    public ResponseEntity<ApiResponse<OrderDetailResponseDto>> getOrderDetail(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long orderId) {
        
        OrderDetailResponseDto response = orderService.getOrderDetail(userId, orderId);
        return ApiResponse.onSuccess(SuccessCode.OK, response);
    }
}
