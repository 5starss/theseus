package com.s14p21a503.matcher.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.ToString;

import java.io.Serializable;
import java.math.BigDecimal;

/**
 * TODO [외부 시세 연동]:
 * 현재는 테스트를 위해 임의의 1호가 데이터(bestBid, bestAsk)만 정의되어 있습니다.
 * 실제 시세 서버(Market Server) 연동 시, 해당 서버에서 내려주는
 * 내려주는 JSON 응답 포맷(필드명, 데이터 타입 등)에 맞게 이 DTO의 필드들을 전면 수정해야 합니다.
 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@ToString
public class MarketDataEvent implements Serializable {
    private static final long serialVersionUID = 1L;
    private String ticker;
    private BigDecimal bestBid; // 최우선 매수 호가
    private BigDecimal bestAsk; // 최우선 매도 호가
    private long timestamp;
}
