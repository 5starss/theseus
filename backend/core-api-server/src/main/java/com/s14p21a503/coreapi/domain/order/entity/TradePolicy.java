package com.s14p21a503.coreapi.domain.order.entity;

import java.math.BigDecimal;

/** 수수료·세금 요율 상수 */
public final class TradePolicy {

    private TradePolicy() {}

    /** 거래 수수료율: 0.015% (매수/매도 공통) */
    public static final BigDecimal FEE_RATE = new BigDecimal("0.00015");

    /** 증권거래세율: 0.20% (매도 전용) */
    public static final BigDecimal TAX_RATE = new BigDecimal("0.002");
}
