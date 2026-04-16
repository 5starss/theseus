package com.s14p21a503.coreapi.domain.market.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 장 중(Market Open) 상태인지 체크하는 마킹용 어노테이션입니다.
 * 이 어노테이션이 붙은 메소드는 실행 전 시장이 열려있는지 확인합니다.
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface CheckMarketOpen {
}
