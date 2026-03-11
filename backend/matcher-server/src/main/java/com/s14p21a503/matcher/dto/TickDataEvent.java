package com.s14p21a503.matcher.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.ToString;

import java.io.Serializable;
import java.math.BigDecimal;

@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@ToString
public class TickDataEvent implements Serializable {
    private static final long serialVersionUID = 1L;
    private String topic;
    private String ticker;
    private String name;
    private BigDecimal price;
    private BigDecimal open;
    private BigDecimal high;
    private BigDecimal low;
    @JsonProperty("change_rate")
    private Double changeRate;
    @JsonProperty("acc_vol")
    private Long accVol;
    @JsonProperty("trade_vol")
    private Long tradeVol;
    private long timestamp; // 리스너 수신 시점 또는 Kafka 헤더 타임스탬프 주입용

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }
}
