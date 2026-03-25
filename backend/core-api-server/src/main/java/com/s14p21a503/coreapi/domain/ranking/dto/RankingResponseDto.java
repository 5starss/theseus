package com.s14p21a503.coreapi.domain.ranking.dto;

import com.s14p21a503.coreapi.common.response.PageResponseDto;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.ranking.entity.DailyRanking;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Getter
@Builder
public class RankingResponseDto {
    private RankingDto myRanking;
    private PageResponseDto<RankingDto> rankings;

    @Getter
    @Builder
    public static class RankingDto {
        private Long userId;
        private Long rank;
        private String nickname;
        private BigDecimal roi;
        private LocalDateTime rankDateTime;
        private Double percentile;

        public static RankingDto from(DailyRanking dailyRanking, long totalCount) {
            double calcPercentile = totalCount > 0 
                ? Math.min((double) dailyRanking.getRankOrder() / totalCount * 100, 100.0)
                : 0.0;
            
            return RankingDto.builder()
                    .userId(dailyRanking.getUserId())
                    .rank(dailyRanking.getRankOrder())
                    .nickname(dailyRanking.getNickname())
                    .roi(dailyRanking.getRoi())
                    .rankDateTime(dailyRanking.getRankDateTime())
                    .percentile(Math.round(calcPercentile * 10.0) / 10.0) // 소수점 첫째자리 반올림
                    .build();
        }
    }
}
