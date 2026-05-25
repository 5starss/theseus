package com.s14p21a503.coreapi.domain.portfolio.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.portfolio.dto.PortfolioSummaryResponseDto;
import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import com.s14p21a503.coreapi.domain.stock.service.StockCurrentPriceService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class PortfolioService {

    private final AccountRepository accountRepository;
    private final PositionRepository positionRepository;
    private final StockCurrentPriceService stockCurrentPriceService;

    @Transactional(readOnly = true)
    public PortfolioSummaryResponseDto getMyPortfolioSummary(Long userId) {
        Account account = accountRepository.findByUserIdAndAccountType(userId, AccountType.USER)
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));

        List<Position> positions = positionRepository.findAllWithStockByAccountId(account.getId()).stream()
                .filter(position -> position.getQuantity() != null && position.getQuantity() > 0)
                .toList();

        if (positions.isEmpty()) {
            return PortfolioSummaryResponseDto.builder()
                    .totalEvaluationAmount(BigDecimal.ZERO)
                    .totalPurchaseAmount(BigDecimal.ZERO)
                    .totalProfitLoss(BigDecimal.ZERO)
                    .totalProfitRate(BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP))
                    .holdingCount(0)
                    .items(List.of())
                    .build();
        }

        Map<String, BigDecimal> currentPriceMap = stockCurrentPriceService.getCurrentPrices(
                positions.stream().map(Position::getTicker).toList()
        );

        List<PortfolioSummaryResponseDto.PortfolioItemDto> preliminaryItems = positions.stream()
                .map(position -> buildItem(position, currentPriceMap.getOrDefault(position.getTicker(), BigDecimal.ZERO), BigDecimal.ZERO))
                .toList();

        BigDecimal totalEvaluationAmount = preliminaryItems.stream()
                .map(PortfolioSummaryResponseDto.PortfolioItemDto::getEvaluationAmount)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal totalPurchaseAmount = preliminaryItems.stream()
                .map(PortfolioSummaryResponseDto.PortfolioItemDto::getPurchaseAmount)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal totalProfitLoss = totalEvaluationAmount.subtract(totalPurchaseAmount);
        BigDecimal totalProfitRate = calculateRate(totalProfitLoss, totalPurchaseAmount);

        List<PortfolioSummaryResponseDto.PortfolioItemDto> items = preliminaryItems.stream()
                .map(item -> PortfolioSummaryResponseDto.PortfolioItemDto.builder()
                        .stockCode(item.getStockCode())
                        .stockName(item.getStockName())
                        .quantity(item.getQuantity())
                        .averagePurchasePrice(item.getAveragePurchasePrice())
                        .currentPrice(item.getCurrentPrice())
                        .purchaseAmount(item.getPurchaseAmount())
                        .evaluationAmount(item.getEvaluationAmount())
                        .profitLoss(item.getProfitLoss())
                        .profitRate(item.getProfitRate())
                        .portfolioWeight(calculateRate(item.getEvaluationAmount(), totalEvaluationAmount))
                        .build())
                .toList();

        return PortfolioSummaryResponseDto.builder()
                .totalEvaluationAmount(totalEvaluationAmount)
                .totalPurchaseAmount(totalPurchaseAmount)
                .totalProfitLoss(totalProfitLoss)
                .totalProfitRate(totalProfitRate)
                .holdingCount(items.size())
                .items(items)
                .build();
    }

    private PortfolioSummaryResponseDto.PortfolioItemDto buildItem(
            Position position,
            BigDecimal currentPrice,
            BigDecimal portfolioWeight
    ) {
        BigDecimal quantity = BigDecimal.valueOf(position.getQuantity());
        BigDecimal purchaseAmount = position.getTotalPurchaseAmount() == null
                ? BigDecimal.ZERO
                : position.getTotalPurchaseAmount();
        BigDecimal evaluationAmount = currentPrice.multiply(quantity);
        BigDecimal profitLoss = evaluationAmount.subtract(purchaseAmount);
        BigDecimal profitRate = calculateRate(profitLoss, purchaseAmount);
        String stockName = position.getStock() != null
                ? position.getStock().getCompanyName()
                : position.getTicker();

        return PortfolioSummaryResponseDto.PortfolioItemDto.builder()
                .stockCode(position.getTicker())
                .stockName(stockName)
                .quantity(position.getQuantity())
                .averagePurchasePrice(position.getAveragePrice())
                .currentPrice(currentPrice)
                .purchaseAmount(purchaseAmount)
                .evaluationAmount(evaluationAmount)
                .profitLoss(profitLoss)
                .profitRate(profitRate)
                .portfolioWeight(portfolioWeight)
                .build();
    }

    private BigDecimal calculateRate(BigDecimal numerator, BigDecimal denominator) {
        if (denominator == null || denominator.signum() == 0) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }

        return numerator.divide(denominator, 6, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100))
                .setScale(2, RoundingMode.HALF_UP);
    }
}
