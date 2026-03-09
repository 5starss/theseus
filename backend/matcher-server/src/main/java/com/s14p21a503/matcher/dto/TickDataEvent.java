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
 * 실제 시세 서버(Market Server)의 체결 데이터 포맷에 맞게 수정이 필요할 수 있습니다.
 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@ToString
public class TickDataEvent implements Serializable {
    private static final long serialVersionUID = 1L;
    private String ticker;
    private BigDecimal price; // 체결가
    private Long qty; // 체결수량
    private long timestamp;
}
