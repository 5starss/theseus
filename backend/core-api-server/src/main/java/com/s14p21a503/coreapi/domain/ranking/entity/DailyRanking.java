package com.s14p21a503.coreapi.domain.ranking.entity;

import com.s14p21a503.coreapi.common.entity.BaseEntity;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Table(name = "daily_rankings",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_daily_rankings_date_user",
                columnNames = {"rank_date", "user_id"}
        ),
        indexes = {
                @Index(name = "idx_daily_rankings_date_roi", columnList = "rank_date, roi DESC"),
                @Index(name = "idx_daily_rankings_nickname_fts", columnList = "nickname")
        }
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class DailyRanking extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "daily_ranking_id")
    private Long id;

    @Column(name = "rank_date", nullable = false)
    private LocalDate rankDate;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "nickname", nullable = false, length = 50)
    private String nickname;

    @Column(name = "roi", precision = 10, scale = 4, nullable = false)
    private BigDecimal roi;

    @Column(name = "rank_order", nullable = false)
    private Long rankOrder;
}
