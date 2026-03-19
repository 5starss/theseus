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
import java.math.RoundingMode;
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
        String stockNameForNotif = order.getStock() != null ? order.getStock().getCompanyName() : event.getTicker();
        eventPublisher.publishEvent(new ExecutionNotificationEvent(event.getUserId(), stockNameForNotif, event));
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
            account.unlockBalance(order.getRemainingLock());
        } else {
            Position position = positionRepository
                    .findByAccountIdAndTickerForUpdate(order.getAccountId(), order.getTicker())
                    .orElseThrow(() -> new CustomException(ErrorCode.POSITION_NOT_FOUND));
            position.unlockQuantity(remainingQuantity);
        }

        // 실시간 알림 전송 (트랜잭션 커밋 후 발송)
        String stockNameForNotif = order.getStock() != null ? order.getStock().getCompanyName() : event.getTicker();
        ExecutionEventDto notificationDto = ExecutionEventDto.builder()
                .executionId(event.getExecutionId())
                .orderId(event.getOrderId())
                .accountId(event.getAccountId())
                .userId(order.getUserId())
                .orderType(order.getOrderType())
                .eventType(EventType.CANCELLED)
                .ticker(order.getTicker())
                .matchPrice(order.getPrice())
                .matchQuantity((long) remainingQuantity)
                .executedAt(LocalDateTime.now())
                .build();
        eventPublisher.publishEvent(new ExecutionNotificationEvent(order.getUserId(), stockNameForNotif, notificationDto));
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
            account.unlockBalance(order.getRemainingLock());
        } else {
            Position position = positionRepository
                    .findByAccountIdAndTickerForUpdate(event.getAccountId(), event.getTicker())
                    .orElseThrow(() -> new CustomException(ErrorCode.POSITION_NOT_FOUND));
            position.unlockQuantity(remainingQuantity);
        }

        // 실시간 알림 전송 (트랜잭션 커밋 후 발송)
        String stockNameForNotif = order.getStock() != null ? order.getStock().getCompanyName() : event.getTicker();
        ExecutionEventDto notificationDto = ExecutionEventDto.builder()
                .executionId(event.getExecutionId())
                .orderId(event.getOrderId())
                .accountId(event.getAccountId())
                .userId(event.getUserId())
                .orderType(event.getOrderType())
                .eventType(event.getEventType())
                .ticker(event.getTicker())
                .matchPrice(order.getPrice())
                .matchQuantity((long) remainingQuantity)
                .executedAt(event.getExecutedAt())
                .build();
        eventPublisher.publishEvent(new ExecutionNotificationEvent(event.getUserId(), stockNameForNotif, notificationDto));
    }

    private void processBuy(ExecutionEventDto event, Account account, Order order, int quantity) {
        BigDecimal executionAmount = event.getMatchPrice().multiply(BigDecimal.valueOf(quantity));
        BigDecimal executionFee    = executionAmount.multiply(TradePolicy.FEE_RATE).setScale(0, RoundingMode.DOWN);

        // FILLED: 잔여 잠금 전액 해제 → 주문가/체결가 차액 및 절사 잔여분 한 번에 환급
        // PARTIAL: 실제 체결 비용만큼만 잠금 해제 → 주문 진행 중 잔고 변동 없음
        BigDecimal lockedCostToRelease;
        if (order.getStatus() == OrderStatus.FILLED) {
            lockedCostToRelease = order.getRemainingLock();
        } else {
            lockedCostToRelease = executionAmount.add(executionFee);
        }

        BigDecimal actualCostWithFee = executionAmount.add(executionFee);

        // 계좌 정산 (체결가 기반 실비용 차감, 잠금 해제, 초과분 환급)
        account.settleBuy(actualCostWithFee, lockedCostToRelease);
        order.releasePartialLock(lockedCostToRelease);

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

        // 원장 거래 내역 저장 (amount = 체결금액 + 수수료)
        String stockName = order.getStock() != null ? order.getStock().getCompanyName() : null;
        accountHistoryRepository.save(AccountHistory.builder()
                .userId(event.getUserId())
                .transactionType(TransactionType.BUY)
                .ticker(event.getTicker())
                .stockName(stockName)
                .quantity(quantity)
                .price(event.getMatchPrice())
                .fee(executionFee)
                .tax(BigDecimal.ZERO)
                .amount(actualCostWithFee)
                .balanceAfter(account.getDncaTotAmt())
                .executedAt(event.getExecutedAt())
                .build());
    }

    private void processSell(ExecutionEventDto event, Account account, Order order, int quantity) {
        BigDecimal grossAmount = event.getMatchPrice().multiply(BigDecimal.valueOf(quantity));
        BigDecimal fee = grossAmount.multiply(TradePolicy.FEE_RATE).setScale(0, RoundingMode.DOWN);
        BigDecimal tax = grossAmount.multiply(TradePolicy.TAX_RATE).setScale(0, RoundingMode.DOWN);

        BigDecimal netProceeds = grossAmount.subtract(fee).subtract(tax);

        // 계좌 정산 (매도 순수익 입금: 체결금액 - 수수료 - 매도세)
        account.settleSell(netProceeds);

        // 포지션 업데이트
        Position position = positionRepository
                .findByAccountIdAndTickerForUpdate(event.getAccountId(), event.getTicker())
                .orElseThrow(() -> new CustomException(ErrorCode.POSITION_NOT_FOUND));

        position.applySell(quantity);

        // 전량 매도 시 포지션 삭제
        if (position.getQuantity() == 0) {
            positionRepository.delete(position);
        }

        // 원장 거래 내역 저장 (amount = 체결금액 - 수수료 - 매도세)
        String stockName = order.getStock() != null ? order.getStock().getCompanyName() : null;
        accountHistoryRepository.save(AccountHistory.builder()
                .userId(event.getUserId())
                .transactionType(TransactionType.SELL)
                .ticker(event.getTicker())
                .stockName(stockName)
                .quantity(quantity)
                .price(event.getMatchPrice())
                .fee(fee)
                .tax(tax)
                .amount(netProceeds)
                .balanceAfter(account.getDncaTotAmt())
                .executedAt(event.getExecutedAt())
                .build());
    }
}
