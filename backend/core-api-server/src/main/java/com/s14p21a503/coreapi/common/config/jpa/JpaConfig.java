package com.s14p21a503.coreapi.common.config.jpa;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

/**
 * JPA 엔티티의 생성 시간과 수정 시간을 자동으로 관리하기 위한 Auditing 설정 클래스입니다.
 */
@Configuration
@EnableJpaAuditing
public class JpaConfig {
}
