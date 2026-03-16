package com.s14p21a503.coreapi.domain.order.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.entity.AccountHistory;
import com.s14p21a503.coreapi.domain.account.entity.TransactionType;
import com.s14p21a503.coreapi.domain.account.repository.AccountHistoryRepository;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.order.dto.ExecutionEventDto;
import com.s14p21a503.coreapi.domain.order.entity.*;
import com.s14p21a503.coreapi.domain.order.repository.ExecutionRepository;
import com.s14p21a503.coreapi.domain.order.repository.OrderHistoryRepository;
import com.s14p21a503.coreapi.domain.order.repository.OrderRepository;
import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import com.s14p21a503.coreapi.domain.notification.event.ExecutionNotificationEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class ExecutionLedgerService {

    private final OrderRepository orderRepository;
    private final ExecutionRepository executionRepository;
    private final OrderHistoryRepository orderHistoryRepository;
    private final AccountRepository accountRepository;
    private final AccountHistoryRepository accountHistoryRepository;
    private final PositionRepository positionRepository;
    private final ApplicationEventPublisher eventPublisher;

    @Transactional
    public void processExecution(ExecutionEventDto event) {
        // 1. 주문 조회 (비관적 락 획득)
        Order order = orderRepository.findByIdForUpdate(event.getOrderId())
                .orElseThrow(() -> new CustomException(ErrorCode.ORDER_NOT_FOUND));

        // 2. 중복 체결 확인 (락 획득 후 최종 검사)
        if (executionRepository.existsById(event.getExecutionId())) {
            log.warn("이미 처리된 체결 ID입니다. 중복 처리를 방지합니다. executionId: {}", event.getExecutionId());
            return;
        }

        // 3. 취소 이벤트 처리
        if (event.getEventType() == EventType.CANCELLED) {
            processCancel(event, order);
            return;
        }

        int quantity = event.getMatchQuantity().intValue();

        // 4. 체결 수량 반영
        order.execute(quantity);

        // 5. 체결 내역 저장 (Persistable.isNew()=true로 항상 INSERT → 동시 중복 시 PK 충돌로 트랜잭션 롤백)
        Execution execution = Execution.builder()
                .id(event.getExecutionId())
                .order(order)
                .executionPrice(event.getMatchPrice())
                .executionQuantity(quantity)
                .executedAt(event.getExecutedAt())
                .build();
        executionRepository.saveAndFlush(execution);

        // 6. 주문 히스토리 저장
        OrderHistory history = OrderHistory.builder()
                .order(order)
                .userId(event.getUserId())
                .ticker(event.getTicker())
                .historyType(HistoryType.EXECUTION)
                .quantity(quantity)
                .price(event.getMatchPrice())
                .createdAt(event.getExecutedAt())
                .build();
        orderHistoryRepository.save(history);

        // 7. 계좌 및 포지션 처리
        Account account = accountRepository.findByUserIdForUpdate(event.getUserId())
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));

        if (event.getOrderType() == OrderType.BUY) {
            processBuy(event, account, order, quantity);
        } else {
            processSell(event, account, order, quantity);
        }

        // 8. 실시간 알림 전송 (트랜잭션 커밋 후 발송)
        eventPublisher.publishEvent(new ExecutionNotificationEvent(event.getUserId(), event));
    }

    @Transactional
    public void processExecutionFailure(ExecutionEventDto event) {
        Order order = orderRepository.findByIdForUpdate(event.getOrderId()).orElse(null);
        if (order == null) {
            log.warn("시스템 취소 처리 실패 - 주문 없음 - orderId: {}", event.getOrderId());
            return;
        }
        if (order.getStatus() == OrderStatus.CANCELLED || order.getStatus() == OrderStatus.FILLED) {
            log.warn("이미 처리된 주문 - orderId: {}, status: {}", event.getOrderId(), order.getStatus());
            return;
        }

        int remainingQuantity = order.getRequestedQuantity() - order.getExecutedQuantity();
        order.cancel();

        OrderHistory history = OrderHistory.builder()
                .order(order)
                .userId(order.getUserId())
                .ticker(order.getTicker())
                .historyType(HistoryType.SYSTEM_CANCELLATION)
                .quantity(remainingQuantity)
                .price(order.getPrice())
                .createdAt(LocalDateTime.now())
                .build();
        orderHistoryRepository.save(history);

        Account account = accountRepository.findByUserIdForUpdate(order.getUserId())
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));

        if (order.getOrderType() == OrderType.BUY) {
            account.unlockBalance(order.getPrice().multiply(BigDecimal.valueOf(remainingQuantity)));
        } else {
            Position position = positionRepository
                    .findByAccountIdAndTickerForUpdate(order.getAccountId(), order.getTicker())
                    .orElseThrow(() -> new CustomException(ErrorCode.POSITION_NOT_FOUND));
            position.unlockQuantity(remainingQuantity);
        }

        // 실시간 알림 전송 (트랜잭션 커밋 후 발송)
        eventPublisher.publishEvent(new ExecutionNotificationEvent(order.getUserId(), event));
    }

    private void processCancel(ExecutionEventDto event, Order order) {
        // 이미 취소됐거나 전량 체결된 경우 무시 (중복 이벤트 또는 race condition 방어)
        if (order.getStatus() == OrderStatus.CANCELLED || order.getStatus() == OrderStatus.FILLED) {
            log.warn("취소 불가 상태의 주문 - orderId: {}, status: {}", event.getOrderId(), order.getStatus());
            return;
        }

        int remainingQuantity = order.getRequestedQuantity() - order.getExecutedQuantity();
        order.cancel();

        // 주문 히스토리 저장
        OrderHistory history = OrderHistory.builder()
                .order(order)
                .userId(event.getUserId())
                .ticker(event.getTicker())
                .historyType(HistoryType.CANCELLATION)
                .quantity(remainingQuantity)
                .price(order.getPrice())
                .createdAt(event.getExecutedAt())
                .build();
        orderHistoryRepository.save(history);

        // 잠금 해제
        Account account = accountRepository.findByUserIdForUpdate(event.getUserId())
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));

        if (event.getOrderType() == OrderType.BUY) {
            BigDecimal refundAmount = order.getPrice().multiply(BigDecimal.valueOf(remainingQuantity));
            account.unlockBalance(refundAmount);
        } else {
            Position position = positionRepository
                    .findByAccountIdAndTickerForUpdate(event.getAccountId(), event.getTicker())
                    .orElseThrow(() -> new CustomException(ErrorCode.POSITION_NOT_FOUND));
            position.unlockQuantity(remainingQuantity);
        }

        // 실시간 알림 전송 (트랜잭션 커밋 후 발송)
        eventPublisher.publishEvent(new ExecutionNotificationEvent(event.getUserId(), event));
    }

    private void processBuy(ExecutionEventDto event, Account account, Order order, int quantity) {
        // 계좌 정산 (lockedAmt 해제, dncaTotAmt 차감, 환급액 반환)
        account.settleBuy(event.getMatchPrice(), quantity, order.getPrice());

        // 포지션 업데이트 (없으면 신규 생성)
        Position position = positionRepository
                .findByAccountIdAndTickerForUpdate(event.getAccountId(), event.getTicker())
                .orElse(null);

        if (position == null) {
            position = Position.builder()
                    .accountId(event.getAccountId())
                    .userId(event.getUserId())
                    .ticker(event.getTicker())
                    .quantity(0)
                    .averagePrice(BigDecimal.ZERO)
                    .totalPurchaseAmount(BigDecimal.ZERO)
                    .build();
            positionRepository.save(position);
        }

        position.applyBuy(quantity, event.getMatchPrice());

        // 원장 거래 내역 저장
        String stockName = order.getStock() != null ? order.getStock().getCompanyName() : null;
        BigDecimal amount = event.getMatchPrice().multiply(BigDecimal.valueOf(quantity));
        accountHistoryRepository.save(AccountHistory.builder()
                .userId(event.getUserId())
                .transactionType(TransactionType.BUY)
                .ticker(event.getTicker())
                .stockName(stockName)
                .quantity(quantity)
                .price(event.getMatchPrice())
                .amount(amount)
                .balanceAfter(account.getDncaTotAmt())
                .executedAt(event.getExecutedAt())
                .build());
    }

    private void processSell(ExecutionEventDto event, Account account, Order order, int quantity) {
        // 계좌 정산 (매도 대금 입금)
        account.settleSell(event.getMatchPrice(), quantity);

        // 포지션 업데이트
        Position position = positionRepository
                .findByAccountIdAndTickerForUpdate(event.getAccountId(), event.getTicker())
                .orElseThrow(() -> new CustomException(ErrorCode.POSITION_NOT_FOUND));

        position.applySell(quantity);

        // 전량 매도 시 포지션 삭제
        if (position.getQuantity() == 0) {
            positionRepository.delete(position);
        }

        // 원장 거래 내역 저장
        String stockName = order.getStock() != null ? order.getStock().getCompanyName() : null;
        BigDecimal amount = event.getMatchPrice().multiply(BigDecimal.valueOf(quantity));
        accountHistoryRepository.save(AccountHistory.builder()
                .userId(event.getUserId())
                .transactionType(TransactionType.SELL)
                .ticker(event.getTicker())
                .stockName(stockName)
                .quantity(quantity)
                .price(event.getMatchPrice())
                .amount(amount)
                .balanceAfter(account.getDncaTotAmt())
                .executedAt(event.getExecutedAt())
                .build());
    }
}
