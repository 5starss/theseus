package com.s14p21a503.coreapi.domain.order.service;

import com.s14p21a503.coreapi.domain.order.dto.OrderRequestDto;
import com.s14p21a503.coreapi.domain.order.dto.OrderResponseDto;
import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.order.dto.OrderRequestDto;
import com.s14p21a503.coreapi.domain.order.dto.OrderResponseDto;
import com.s14p21a503.coreapi.domain.order.entity.Order;
import com.s14p21a503.coreapi.domain.order.entity.PriceType;
import com.s14p21a503.coreapi.domain.order.repository.OrderRepository;
import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;

import com.s14p21a503.coreapi.domain.outbox.entity.OutboxEvent;
import com.s14p21a503.coreapi.domain.outbox.repository.OutboxEventRepository;
import com.s14p21a503.coreapi.domain.order.dto.OrderEventDto;
import com.s14p21a503.coreapi.common.kafka.KafkaTopicConstants;
import com.fasterxml.jackson.databind.ObjectMapper;

import com.s14p21a503.coreapi.common.exception.BaseException;
import com.s14p21a503.coreapi.common.exception.ErrorCode;

@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final PositionRepository positionRepository;
    private final AccountRepository accountRepository;
    private final OutboxEventRepository outboxEventRepository;
    private final ObjectMapper objectMapper;

    public OrderService(OrderRepository orderRepository, PositionRepository positionRepository, AccountRepository accountRepository, OutboxEventRepository outboxEventRepository, ObjectMapper objectMapper) {
        this.orderRepository = orderRepository;
        this.positionRepository = positionRepository;
        this.accountRepository = accountRepository;
        this.outboxEventRepository = outboxEventRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public OrderResponseDto createOrder(Long userId, OrderRequestDto requestDto) {
        // 비관적 락으로 계좌 정보를 조회 (트랜잭션 종료 시까지 락 유지)
        Account account = accountRepository.findByUserIdForUpdate(userId)
                .orElseThrow(() -> new BaseException(ErrorCode.ACCOUNT_NOT_FOUND));

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
                    .orElseThrow(() -> new BaseException(ErrorCode.POSITION_NOT_FOUND));

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
            OrderEventDto eventDto = OrderEventDto.from(savedOrder);
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
            throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR, e);
        }

        // Response DTO로 변환하여 리턴
        return OrderResponseDto.from(savedOrder);
    }
}
