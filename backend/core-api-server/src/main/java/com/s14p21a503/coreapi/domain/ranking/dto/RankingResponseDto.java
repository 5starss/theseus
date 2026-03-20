package com.s14p21a503.coreapi.domain.ranking.dto;

import com.s14p21a503.coreapi.common.response.PageResponseDto;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.ranking.entity.DailyRanking;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;

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
        private LocalDate rankDate;

        public static RankingDto from(DailyRanking dailyRanking) {
            return RankingDto.builder()
                    .userId(dailyRanking.getUserId())
                    .rank(dailyRanking.getRankOrder())
                    .nickname(dailyRanking.getNickname())
                    .roi(dailyRanking.getRoi())
                    .rankDate(dailyRanking.getRankDate())
                    .build();
        }
    }
}
