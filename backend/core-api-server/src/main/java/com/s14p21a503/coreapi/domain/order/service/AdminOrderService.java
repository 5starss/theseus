package com.s14p21a503.coreapi.domain.order.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.order.dto.AdminForceExecuteDto;
import com.s14p21a503.coreapi.domain.order.dto.ExecutionEventDto;
import com.s14p21a503.coreapi.domain.order.entity.EventType;
import com.s14p21a503.coreapi.domain.order.entity.Order;
import com.s14p21a503.coreapi.domain.order.repository.OrderRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class AdminOrderService {

    private final OrderRepository orderRepository;
    private final ExecutionLedgerService executionLedgerService;

    @Transactional
    public void forceCancelOrder(Long orderId) {
        log.info("관리자 권한 - 주문 강제 취소 요청: {}", orderId);
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new CustomException(ErrorCode.ORDER_NOT_FOUND));

        // 취소 실패 로직(DLQ에서 쓰는 롤백 로직)과 동일하게 상태 복원 및 실패 처리 이벤트 발송
        ExecutionEventDto dummyEvent = ExecutionEventDto.builder()
                .executionId(System.currentTimeMillis()) // 임의의 고유 ID
                .orderId(order.getId())
                .accountId(order.getAccountId())
                .userId(order.getUserId())
                .orderType(order.getOrderType())
                .eventType(EventType.CANCELLED)
                .ticker(order.getTicker())
                .matchPrice(order.getPrice())
                .matchQuantity(0L)
                .remainingQuantity(0L)
                .executedAt(LocalDateTime.now())
                .build();

        executionLedgerService.processExecutionFailure(dummyEvent);
        log.info("관리자 권한 - 주문 강제 취소 처리 완료: {}", orderId);
    }

    @Transactional
    public void forceExecuteOrder(Long orderId, AdminForceExecuteDto request) {
        log.info("관리자 권한 - 주문 강제 체결 요청: {}, 수량: {}, 가격: {}", orderId, request.getQuantity(), request.getPrice());
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new CustomException(ErrorCode.ORDER_NOT_FOUND));

        if (request.getQuantity() <= 0 || request.getPrice() == null) {
            throw new CustomException(ErrorCode.INVALID_REQUEST);
        }

        ExecutionEventDto dummyEvent = ExecutionEventDto.builder()
                .executionId(System.currentTimeMillis()) // 임의의 고유 ID
                .orderId(order.getId())
                .accountId(order.getAccountId())
                .userId(order.getUserId())
                .orderType(order.getOrderType())
                .eventType(EventType.MATCHED)
                .ticker(order.getTicker())
                .matchPrice(request.getPrice())
                .matchQuantity((long) request.getQuantity())
                .remainingQuantity((long) Math.max(0, order.getRequestedQuantity() - order.getExecutedQuantity() - request.getQuantity()))
                .executedAt(LocalDateTime.now())
                .build();

        executionLedgerService.processExecution(dummyEvent);
        log.info("관리자 권한 - 주문 강제 체결 처리 완료: {}", orderId);
    }
}
