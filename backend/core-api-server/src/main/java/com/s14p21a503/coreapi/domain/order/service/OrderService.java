package com.s14p21a503.coreapi.domain.order.service;

import com.s14p21a503.coreapi.domain.order.dto.*;
import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.order.entity.Order;
import com.s14p21a503.coreapi.domain.order.entity.OrderStatus;
import com.s14p21a503.coreapi.domain.order.entity.HistoryType;
import com.s14p21a503.coreapi.domain.order.repository.OrderRepository;
import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.s14p21a503.coreapi.domain.order.repository.OrderHistoryRepository;
import com.s14p21a503.coreapi.common.response.PageResponseDto;
import com.s14p21a503.coreapi.domain.order.entity.OrderHistory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Arrays;
import java.util.List;

import java.math.BigDecimal;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;

import com.s14p21a503.coreapi.domain.outbox.entity.OutboxEvent;
import com.s14p21a503.coreapi.domain.outbox.repository.OutboxEventRepository;
import com.s14p21a503.coreapi.common.kafka.KafkaTopicConstants;
import com.fasterxml.jackson.databind.ObjectMapper;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;

@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final OrderHistoryRepository orderHistoryRepository;
    private final PositionRepository positionRepository;
    private final AccountRepository accountRepository;
    private final OutboxEventRepository outboxEventRepository;
    private final ObjectMapper objectMapper;

    @Transactional
    public OrderResponseDto createOrder(Long userId, OrderRequestDto requestDto) {
        // 비관적 락으로 계좌 정보를 조회 (트랜잭션 종료 시까지 락 유지)
        Account account = accountRepository.findByUserIdForUpdate(userId)
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));

        // 매수 주문 시 증거금 체크 및 잠금(Lock)
        if (requestDto.getOrderType() == OrderType.BUY) {
            BigDecimal totalOrderAmount = requestDto.getPrice().multiply(new BigDecimal(requestDto.getQuantity()));
            // 엔티티 내부에서 가용 잔고(availableAmt) 확인 후 잠금 처리 (부족 시 BaseException 발생)
            account.lockBalance(totalOrderAmount);
        }
        // 매도 주문 시 보유 주식 체크 및 잠금(Lock)
        else if (requestDto.getOrderType() == OrderType.SELL) {
            // 비관적 락으로 해당 계좌가 가지는 주식 포지션 갯수 조회
            Position position = positionRepository.findByAccountIdAndTickerForUpdate(account.getId(), requestDto.getTicker())
                    .orElseThrow(() -> new CustomException(ErrorCode.POSITION_NOT_FOUND));

            // 엔티티 내부에서 가용 주식(availableQuantity) 확인 후 잠금 처리 (부족 시 BaseException 발생)
            position.lockQuantity(requestDto.getQuantity());
        }

        // 엔티티 생성
        Order order = Order.builder()
                .accountId(account.getId())
                .userId(userId)
                .ticker(requestDto.getTicker())
                .orderType(requestDto.getOrderType())
                .priceType(requestDto.getPriceType())
                .price(requestDto.getPrice())
                .requestedQuantity(requestDto.getQuantity())
                .build();

        // 데이터베이스에 저장
        Order savedOrder = orderRepository.save(order);

        // 아웃박스 패턴: 동일한 트랜잭션 내에서 카프카 이벤트를 아웃박스 테이블에 추가
        try {
            OrderEventDto eventDto = OrderEventDto.from(savedOrder, "CREATE");
            String payloadJson = objectMapper.writeValueAsString(eventDto);

            OutboxEvent outboxEvent = OutboxEvent.builder()
                    .aggregateType("ORDER")
                    .aggregateId(String.valueOf(savedOrder.getId()))
                    .topic(KafkaTopicConstants.ORDER_EVENT_TOPIC)
                    .messageKey(savedOrder.getTicker())
                    .payload(payloadJson)
                    .build();
            outboxEventRepository.save(outboxEvent);
        } catch (Exception e) {
            throw new CustomException(ErrorCode.INTERNAL_SERVER_ERROR, e);
        }

        // Response DTO로 변환하여 리턴
        return OrderResponseDto.from(savedOrder);
    }

    /**
     * 주문 내역(대기/완료)을 조회합니다.
     * 프론트엔드 기획에 맞춰 대기건(Order 기준)과 완료건(Execution 기준) 테이블을 분리하여 조회하고,
     * 하나의 응답 DTO(OrderHistoryResponseDto)에 예쁘게 담아서 반환합니다.
     */
    @Transactional(readOnly = true)
    public OrderHistoryResponseDto getOrders(
            Long userId, String filter, String ticker, LocalDateTime startDate, LocalDateTime endDate, Pageable pageable) {

        // 프론트로 내려갈 두 가지 종류의 페이지 응답 객체입니다. (기본값 null)
        PageResponseDto<PendingOrderDto> pendingPage = null;
        PageResponseDto<OrderHistoryDto> completedPage = null;

        // 1. 대기 탭 검색이거나 전체 보기일 때 작동
        if ("PENDING".equals(filter) || "ALL".equals(filter)) {
            // 대기 쿼리: Order 테이블 기준으로 OPEN, PARTIAL, PENDING_CANCEL 만 검색하고 과거순(최신 요청순)으로 뽑아옵니다.
            List<OrderStatus> statuses = Arrays.asList(OrderStatus.OPEN, OrderStatus.PARTIAL, OrderStatus.PENDING_CANCEL);
            Page<Order> orderPage = orderRepository.searchOrdersByConditions(
                    userId, true, statuses, ticker, startDate, endDate, pageable);
            pendingPage = PageResponseDto.from(orderPage.map(PendingOrderDto::from));
        }

        // 2. 완료 탭 검색이거나 전체 보기일 때 작동
        if ("COMPLETED".equals(filter) || "ALL".equals(filter)) {
            // 완료 쿼리: OrderHistory 테이블(체결/취소 내역) 기준으로 무조건 타임라인 역순(최신순)으로 뽑아옵니다.
            Page<OrderHistory> historyPage = orderHistoryRepository.searchHistoryByConditions(
                    userId, ticker, startDate, endDate, pageable);
            completedPage = PageResponseDto.from(historyPage.map(OrderHistoryDto::from));
        }
        
        // 3. 만들어진 두 가지 목록을 하나의 Wrapper DTO에 넣어서 최종 반환합니다.
        return OrderHistoryResponseDto.builder()
                .pending(pendingPage)
                .completed(completedPage)
                .build();
    }

    @Transactional
    public void cancelOrder(Long userId, Long orderId) {
        Order order = orderRepository.findByIdForUpdate(orderId)
                .orElseThrow(() -> new CustomException(ErrorCode.ORDER_NOT_FOUND));

        if (!order.getUserId().equals(userId)) {
            throw new CustomException(ErrorCode.ACCESS_DENIED);
        }

        if (order.getStatus() != OrderStatus.OPEN && order.getStatus() != OrderStatus.PARTIAL) {
            throw new CustomException(ErrorCode.INVALID_ORDER_STATUS);
        }

        // 1. 상태를 취소 대기(PENDING_CANCEL)로만 변경
        order.pendingCancel();

        // 2. Outbox 이벤트 발행
        try {
            OrderEventDto eventDto = OrderEventDto.from(order, "CANCEL");
            String payloadJson = objectMapper.writeValueAsString(eventDto);

            OutboxEvent outboxEvent = OutboxEvent.builder()
                    .aggregateType("ORDER")
                    .aggregateId(String.valueOf(order.getId()))
                    .topic(KafkaTopicConstants.ORDER_EVENT_TOPIC)
                    .messageKey(order.getTicker())
                    .payload(payloadJson)
                    .build();
            outboxEventRepository.save(outboxEvent);
        } catch (Exception e) {
            throw new CustomException(ErrorCode.INTERNAL_SERVER_ERROR, e);
        }
    }

    @Transactional(readOnly = true)
    public OrderHistoryDetailResponseDto getHistoryDetail(Long userId, Long historyId) {
        OrderHistory history = orderHistoryRepository.findById(historyId)
                .orElseThrow(() -> new CustomException(ErrorCode.EXECUTION_NOT_FOUND));

        if (!history.getUserId().equals(userId)) {
            throw new CustomException(ErrorCode.ACCESS_DENIED);
        }

        return OrderHistoryDetailResponseDto.from(history);
    }

    @Transactional(readOnly = true)
    public OrderDetailResponseDto getOrderDetail(Long userId, Long orderId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new CustomException(ErrorCode.ORDER_NOT_FOUND));

        if (!order.getUserId().equals(userId)) {
            throw new CustomException(ErrorCode.ACCESS_DENIED);
        }

        return OrderDetailResponseDto.from(order);
    }
}
