package com.s14p21a503.coreapi.domain.portfolio.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.util.List;

@Getter
@Builder
public class PortfolioSummaryResponseDto {

    private BigDecimal totalEvaluationAmount;
    private BigDecimal totalPurchaseAmount;
    private BigDecimal totalProfitLoss;
    private BigDecimal totalProfitRate;
    private int holdingCount;
    private List<PortfolioItemDto> items;

    @Getter
    @Builder
    public static class PortfolioItemDto {
        private String stockCode;
        private String stockName;
        private Integer quantity;
        private BigDecimal averagePurchasePrice;
        private BigDecimal currentPrice;
        private BigDecimal purchaseAmount;
        private BigDecimal evaluationAmount;
        private BigDecimal profitLoss;
        private BigDecimal profitRate;
        private BigDecimal portfolioWeight;
    }
}
