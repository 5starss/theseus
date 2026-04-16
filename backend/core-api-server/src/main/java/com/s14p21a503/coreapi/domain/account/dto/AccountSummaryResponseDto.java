package com.s14p21a503.coreapi.domain.account.dto;

import com.s14p21a503.coreapi.domain.position.entity.Position;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Optional;

@Getter
@Builder
public class AccountSummaryResponseDto {
    private Long accountId;
    private BigDecimal totalAmt;  // 예수금 + 주식 평가금
    private BigDecimal availableAmt;  // 주문 가능 현금
    private BigDecimal lockedAmt;     // 주문 대기 중 잠긴 금액
    private BigDecimal totalUnrealizedPnL; // 전체 평가 손익 (평가금액 합계 - 매수금액 합계)
    private BigDecimal totalReturnRate; // 전체 수익률 (%)
    private boolean priceDataAvailable; // 시세 데이터 정상 여부

    // Position 테이블 정보 기반
    private List<StockPositionDto> positions;

    @Getter
    @Builder
    // 개별 종목 정보를 담는 내부 클래스
    public static class StockPositionDto {
        private String ticker;  // 종목 코드
        private String companyName; // 종목명
        private Integer quantity;   // 보유 수량
        private BigDecimal averagePrice;    // 매수 평단가
        private BigDecimal currentPrice;    // 현재가 (Redis에서 가져온 실시간 가격)
        private BigDecimal evaluatedAmount; // 평가금액 (현재가 × 보유 수량)
        private BigDecimal unrealizedPnL;   // 평가손익 (평가금액 - 매수금액)
        private BigDecimal returnRate;      // 종목별 수익률 (%)

        public static StockPositionDto from(Position position, BigDecimal currentPrice) {
            BigDecimal quantity = BigDecimal.valueOf(position.getQuantity());
            BigDecimal totalPurchaseAmount = position.getTotalPurchaseAmount();

            // 평가 금액 및 손익 계산 (currentPrice가 있을 때만)
            BigDecimal evaluatedAmount = Optional.ofNullable(currentPrice)
                    .map(price -> price.multiply(quantity))
                    .orElse(null);

            BigDecimal unrealizedPnL = Optional.ofNullable(evaluatedAmount)
                    .map(evaluated -> evaluated.subtract(totalPurchaseAmount))
                    .orElse(null);

            BigDecimal returnRate = Optional.ofNullable(unrealizedPnL)
                    .filter(pnl -> totalPurchaseAmount.signum() != 0)
                    .map(pnl -> pnl
                            .divide(totalPurchaseAmount, 4, RoundingMode.HALF_UP)
                            .multiply(BigDecimal.valueOf(100))
                            .setScale(2, RoundingMode.HALF_UP))
                    .orElse(null);

            String companyName = position.getStock() != null
                    ? position.getStock().getCompanyName()
                    : position.getTicker();

            return StockPositionDto.builder()
                    .ticker(position.getTicker())
                    .companyName(companyName)
                    .quantity(position.getQuantity())
                    .averagePrice(position.getAveragePrice())
                    .currentPrice(currentPrice)
                    .evaluatedAmount(evaluatedAmount)
                    .unrealizedPnL(unrealizedPnL)
                    .returnRate(returnRate)
                    .build();
        }
    }

}
