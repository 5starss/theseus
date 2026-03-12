package com.s14p21a503.coreapi.domain.market.aop;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.market.service.MarketStateManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Before;
import org.springframework.stereotype.Component;

@Slf4j
@Aspect
@Component
@RequiredArgsConstructor
public class MarketStatusAspect {

    private final MarketStateManager marketStateManager;

    /**
     * @CheckMarketOpen 어노테이션이 붙은 메소드 실행 전에 시장 상태를 확인합니다.
     */
    @Before("@annotation(com.s14p21a503.coreapi.domain.market.annotation.CheckMarketOpen)")
    public void checkMarketStatus() {
        if (!marketStateManager.isMarketOpen()) {
            log.warn("[AOP] 시장이 닫혀있어 요청이 거절되었습니다.");
            throw new CustomException(ErrorCode.MARKET_CLOSED);
        }
    }
}
