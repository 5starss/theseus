package com.s14p21a503.coreapi.domain.account.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.PageResponseDto;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.account.dto.*;
import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.common.infra.redis.RedisService;
import com.s14p21a503.coreapi.domain.account.entity.AccountHistory;
import com.s14p21a503.coreapi.domain.account.entity.TransactionType;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.account.repository.AccountHistoryRepository;
import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.YearMonth;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AccountService {

    private final AccountRepository accountRepository;
    private final AccountHistoryRepository accountHistoryRepository;
    private final PositionRepository positionRepository;
    private final RedisService redisService;

    @Transactional
    public void createAccount(Long userId) {
        // USER 계좌 생성 (1억 원)
        Account userAccount = Account.builder()
                .userId(userId)
                .accountType(AccountType.USER)
                .dncaTotAmt(new BigDecimal("100000000"))
                .build();

        // AI 계좌 생성 (0원)
        Account aiAccount = Account.builder()
                .userId(userId)
                .accountType(AccountType.AI)
                .dncaTotAmt(BigDecimal.ZERO)
                .build();

        accountRepository.save(userAccount);
        accountRepository.save(aiAccount);
        log.info("새로운 계좌 생성 완료 (USER: 1억, AI: 0) - userId: {}", userId);
    }

    @Transactional(readOnly = true)
    public AccountHistoryResponseDto getHistories(Long userId, AccountType accountType, Integer year, Integer month, Pageable pageable) {
        AccountType type = accountType != null ? accountType : AccountType.USER;
        Account account = accountRepository.findByUserIdAndAccountType(userId, type)
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));

        Page<AccountHistory> historyPage;

        // 1) 연/월 필터링이 있는 경우
        if (year != null && month != null) {
            YearMonth yearMonth = YearMonth.of(year, month);
            LocalDateTime startOfMonth = yearMonth.atDay(1).atStartOfDay();
            LocalDateTime endOfMonth = yearMonth.atEndOfMonth().atTime(LocalTime.MAX);

            historyPage = accountHistoryRepository
                    .findAllByAccountIdAndExecutedAtBetweenOrderByExecutedAtDesc(account.getId(), startOfMonth, endOfMonth, pageable);
        }
        // 2) 전체 기간 조회
        else {
            historyPage = accountHistoryRepository.findAllByAccountIdOrderByExecutedAtDesc(account.getId(), pageable);
        }

        return AccountHistoryResponseDto.builder()
                .year(year)
                .month(month)
                .histories(PageResponseDto.from(historyPage.map(AccountHistoryResponseDto.HistoryDto::from)))
                .build();
    }

    @Transactional(readOnly = true)
    public AccountBalanceResponseDto getBalance(Long userId, AccountType accountType) {
        AccountType type = accountType != null ? accountType : AccountType.USER;
        Account account = accountRepository.findByUserIdAndAccountType(userId, type)
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));
        return AccountBalanceResponseDto.from(account);
    }

    @Transactional(readOnly = true)
    public AccountSummaryResponseDto getSummary(Long userId, AccountType accountType) {
        AccountType type = accountType != null ? accountType : AccountType.USER;
        Account account = accountRepository.findByUserIdAndAccountType(userId, type)
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));

        List<Position> positions = positionRepository.findAllWithStockByUserId(userId);

        // 보유 종목 현재가 일괄 조회 (Pipeline)
        Map<String, BigDecimal> priceMap = getCurrentPrices(positions);

        List<AccountSummaryResponseDto.StockPositionDto> positionDtos = positions.stream()
                .map(position -> AccountSummaryResponseDto.StockPositionDto.from(
                        position, priceMap.get(position.getTicker())))
                .toList();

        BigDecimal totalPurchaseAmt = positions.stream()
                .map(Position::getTotalPurchaseAmount)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal totalEvaluatedAmt = positionDtos.stream()
                .map(p -> p.getEvaluatedAmount() != null ? p.getEvaluatedAmount() : BigDecimal.ZERO)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        boolean isAllPriceDataValid = !positions.isEmpty() && positionDtos.stream()
                .allMatch(p -> p.getCurrentPrice() != null && p.getCurrentPrice().compareTo(BigDecimal.ZERO) > 0);

        BigDecimal totalAmt;
        BigDecimal totalUnrealizedPnL = null;
        BigDecimal totalReturnRate = null;

        if (isAllPriceDataValid && totalPurchaseAmt.signum() != 0) {
            totalAmt = account.getDncaTotAmt().add(totalEvaluatedAmt);
            totalUnrealizedPnL = totalEvaluatedAmt.subtract(totalPurchaseAmt);
            totalReturnRate = totalUnrealizedPnL
                    .divide(totalPurchaseAmt, 4, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100))
                    .setScale(2, RoundingMode.HALF_UP);
        } else {
            totalAmt = account.getDncaTotAmt();
        }

        return AccountSummaryResponseDto.builder()
                .accountId(account.getId())
                .totalAmt(totalAmt)
                .availableAmt(account.getAvailableAmt())
                .lockedAmt(account.getLockedAmt())
                .totalUnrealizedPnL(totalUnrealizedPnL)
                .totalReturnRate(totalReturnRate)
                .priceDataAvailable(isAllPriceDataValid)
                .positions(positionDtos)
                .build();
    }

    // 보유 종목 전체 현재가를 Pipeline으로 일괄 조회 → ticker : currentPrice 맵 반환
    private Map<String, BigDecimal> getCurrentPrices(List<Position> positions) {
        if (positions.isEmpty()) return Map.of();

        List<String> tickers = positions.stream()
                .map(Position::getTicker)
                .toList();

        // 1순위: stocks:current:{ticker} → price (실시간 체결가)
        List<String> currentKeys = tickers.stream()
                .map(t -> "stocks:current:" + t)
                .collect(Collectors.toList());
        Map<String, String> currentResults = redisService.getHashFieldBulk(currentKeys, "price");

        // fallback 대상: stocks:current에 없는 ticker
        List<String> fallbackTickers = tickers.stream()
                .filter(t -> !currentResults.containsKey("stocks:current:" + t))
                .toList();

        Map<String, String> infoResults = Map.of();
        if (!fallbackTickers.isEmpty()) {
            List<String> infoKeys = fallbackTickers.stream()
                    .map(t -> "stocks:info:" + t)
                    .collect(Collectors.toList());
            infoResults = redisService.getHashFieldBulk(infoKeys, "currentPrice");
        }

        // ticker → BigDecimal 가격 맵 조합
        Map<String, String> finalInfoResults = infoResults;
        Map<String, BigDecimal> priceMap = new HashMap<>();
        for (String ticker : tickers) {
            String price = currentResults.getOrDefault("stocks:current:" + ticker,
                    finalInfoResults.get("stocks:info:" + ticker));
            if (price == null) {
                log.warn("Redis 시세 누락 - ticker: {} (stocks:current, stocks:info 모두 없음)", ticker);
            } else {
                try {
                    priceMap.put(ticker, new BigDecimal(price));
                } catch (NumberFormatException e) {
                    log.warn("Redis 가격 파싱 실패 - ticker: {}, value: '{}'", ticker, price);
                }
            }
        }
        return priceMap;
    }

    @Transactional
    public void transfer(Long userId, TransferRequestDto requestDto) {
        if (requestDto.getFromType() == requestDto.getToType()) {
            throw new CustomException(ErrorCode.INVALID_REQUEST);
        }

        BigDecimal amount = requestDto.getAmount();
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new CustomException(ErrorCode.INVALID_REQUEST);
        }

        List<Account> lockedAccounts = accountRepository.findAllByUserIdAndAccountTypesForUpdate(
                userId, List.of(requestDto.getFromType(), requestDto.getToType()));

        if (lockedAccounts.size() < 2) {
            throw new CustomException(ErrorCode.ACCOUNT_NOT_FOUND);
        }

        // 실제 송금에 필요한 from/to 계좌 매칭
        Account fromAccount = lockedAccounts.stream()
                .filter(a -> a.getAccountType() == requestDto.getFromType())
                .findFirst().orElseThrow();
        Account toAccount = lockedAccounts.stream()
                .filter(a -> a.getAccountType() == requestDto.getToType())
                .findFirst().orElseThrow();

        // 출금 및 입금 실행
        fromAccount.withdraw(amount);
        toAccount.deposit(amount);

        // 거래 내역 기록
        AccountHistory fromHistory = AccountHistory.builder()
                .accountId(fromAccount.getId())
                .userId(userId)
                .transactionType(TransactionType.WITHDRAWAL)
                .amount(amount.negate())
                .balanceAfter(fromAccount.getDncaTotAmt())
                .executedAt(LocalDateTime.now())
                .build();

        AccountHistory toHistory = AccountHistory.builder()
                .accountId(toAccount.getId())
                .userId(userId)
                .transactionType(TransactionType.DEPOSIT)
                .amount(amount)
                .balanceAfter(toAccount.getDncaTotAmt())
                .executedAt(LocalDateTime.now())
                .build();

        accountHistoryRepository.save(fromHistory);
        accountHistoryRepository.save(toHistory);

        log.info("계좌 간 송금 완료 - userId: {}, from: {}, to: {}, amount: {}", 
                userId, requestDto.getFromType(), requestDto.getToType(), amount);
    }
}
