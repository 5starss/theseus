package com.s14p21a503.coreapi.domain.market.entity;

import com.s14p21a503.coreapi.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDate;

/**
 * 휴장일 엔티티.
 * 관리자가 직접 DB에 입력하거나 API를 통해 등록한 휴장일 정보를 영속화합니다.
 */
@Entity
@Table(name = "holidays")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class Holiday extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "holiday_id")
    private Long id;

    @Column(name = "holiday_date", nullable = false, unique = true)
    private LocalDate date;

    @Column(name = "description", length = 100)
    private String description;

    public void updateDescription(String description) {
        this.description = description;
    }
}
