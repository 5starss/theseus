package com.s14p21a503.coreapi.domain.ranking.service;

import com.s14p21a503.coreapi.common.infra.redis.RedisService;
import com.s14p21a503.coreapi.common.response.PageResponseDto;
import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import com.s14p21a503.coreapi.domain.ranking.dto.RankingResponseDto;
import com.s14p21a503.coreapi.domain.ranking.entity.DailyRanking;
import com.s14p21a503.coreapi.domain.ranking.repository.DailyRankingRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class RankingService {

    private final AccountRepository accountRepository;
    private final PositionRepository positionRepository;
    private final DailyRankingRepository dailyRankingRepository;
    private final RedisService redisService;
    private final RankingCacheService rankingCacheService;

    // 초기 자산
    private static final BigDecimal INITIAL_BALANCE = new BigDecimal("100000000");

    /**
     * 매일 전 유저의 자산을 계산하여 랭킹 스냅샷을 생성합니다.
     */
    @Transactional
    @CacheEvict(value = {"ranking_page", "latest_ranking_date", "user_ranking"}, allEntries = true)
    public void createDailySnapshot() {
        LocalDate today = LocalDate.now();
        log.info("일간 랭킹 스냅샷 생성 시작 - 날짜: {}", today);

        // 1. 모든 계좌와 닉네임 조회 (JOIN FETCH 형식의 쿼리 활용)
        List<Object[]> acctNickList = accountRepository.findAllWithNickname();
        
        // 2. 모든 포지션 조회 및 계좌별 그룹화
        List<Position> allPositions = positionRepository.findAll();
        Map<Long, List<Position>> positionsByAccountId = allPositions.stream()
                .collect(Collectors.groupingBy(Position::getAccountId));

        // 3. 모든 보유 종목의 현재가 조회 (Redis Bulk 조회)
        Set<String> tickers = allPositions.stream()
                .map(Position::getTicker)
                .collect(Collectors.toSet());
        Map<String, BigDecimal> currentPrices = getCurrentPrices(tickers);

        // 4. 유저별(userId)로 계좌 그룹화 및 통합 자산/ROI 계산
        Map<Long, List<Object[]>> acctsByUserId = acctNickList.stream()
                .collect(Collectors.groupingBy(row -> ((Account) row[0]).getUserId()));

        List<DailyRanking> rankingsData = new ArrayList<>();
        for (Map.Entry<Long, List<Object[]>> entry : acctsByUserId.entrySet()) {
            Long userId = entry.getKey();
            List<Object[]> userAcctRows = entry.getValue();
            
            String nickname = (String) userAcctRows.get(0)[1];
            BigDecimal totalUserAssets = BigDecimal.ZERO;

            for (Object[] row : userAcctRows) {
                Account account = (Account) row[0];
                
                // 해당 계좌의 현금 자산 합산
                totalUserAssets = totalUserAssets.add(account.getDncaTotAmt());
                
                // 해당 계좌의 주식 가치 합산
                List<Position> userPositions = positionsByAccountId.getOrDefault(account.getId(), Collections.emptyList());
                for (Position p : userPositions) {
                    BigDecimal price = currentPrices.getOrDefault(p.getTicker(), BigDecimal.ZERO);
                    totalUserAssets = totalUserAssets.add(price.multiply(BigDecimal.valueOf(p.getQuantity())));
                }
            }
            
            // 통합 ROI 계산: ((인간 총 자산 + AI 총 자산) - 초기 자산 1억) / 초기 자산 1억 * 100
            BigDecimal roi = totalUserAssets.subtract(INITIAL_BALANCE)
                    .divide(INITIAL_BALANCE, 6, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100))
                    .setScale(4, RoundingMode.HALF_UP);

            rankingsData.add(DailyRanking.builder()
                    .rankDate(today)
                    .userId(userId)
                    .nickname(nickname)
                    .roi(roi)
                    .rankOrder(0L) // 정렬 전 임시 값
                    .build());
        }

        // 5. ROI 기준 내림차순 정렬 및 순위 부여
        rankingsData.sort(Comparator.comparing(DailyRanking::getRoi).reversed());
        List<DailyRanking> finalRankings = new ArrayList<>();
        for (int i = 0; i < rankingsData.size(); i++) {
            DailyRanking r = rankingsData.get(i);
            finalRankings.add(DailyRanking.builder()
                    .rankDate(r.getRankDate())
                    .userId(r.getUserId())
                    .nickname(r.getNickname())
                    .roi(r.getRoi())
                    .rankOrder((long) (i + 1))
                    .build());
        }

        // 6. 오늘 날짜의 기존 데이터가 있다면 삭제 (멱등성 보장) 후 저장
        dailyRankingRepository.deleteAllByRankDate(today);
        dailyRankingRepository.flush();
        dailyRankingRepository.saveAll(finalRankings);
        log.info("일간 랭킹 스냅샷 생성 완료 - 총 {}명", finalRankings.size());
    }

    /**
     * 최신 랭킹 목록 및 특정 유저의 랭킹 정보를 조회합니다.
     */
    @Transactional(readOnly = true)
    public RankingResponseDto getRankings(Long userId, String nickname, Pageable pageable) {
        // 1. 최신 랭킹 날짜 조회 (로컬 캐싱 적용)
        LocalDate latestDate = rankingCacheService.getLatestDate();

        // 2. 전체 페이징 목록 조회 (순위순, 닉네임 필터 적용 가능) - 로컬 캐싱 적용
        Page<DailyRanking> page = rankingCacheService.getRankingPage(latestDate, nickname, pageable);
        
        // 3. 전체 유저 수 조회 (퍼센트 계산용)
        long totalCount = rankingCacheService.getTotalCount(latestDate);

        // 4. 현재 요청한 유저의 개인 랭킹 정보 조회 (로그인 시에만)
        RankingResponseDto.RankingDto myRankingDto = null;
        if (userId != null) {
            myRankingDto = rankingCacheService.getUserRanking(latestDate, userId)
                    .map(r -> RankingResponseDto.RankingDto.from(r, totalCount))
                    .orElse(null);
        }

        return RankingResponseDto.builder()
                .myRanking(myRankingDto)
                .rankings(PageResponseDto.from(page.map(r -> RankingResponseDto.RankingDto.from(r, totalCount))))
                .build();
    }

    private Map<String, BigDecimal> getCurrentPrices(Set<String> tickers) {
        if (tickers.isEmpty()) return Map.of();
        
        List<String> currentKeys = tickers.stream()
                .map(t -> "stocks:current:" + t)
                .collect(Collectors.toList());
        Map<String, String> currentResults = redisService.getHashFieldBulk(currentKeys, "price");

        Map<String, BigDecimal> priceMap = new HashMap<>();
        for (String ticker : tickers) {
            String price = currentResults.get("stocks:current:" + ticker);
            if (price != null) {
                try {
                    priceMap.put(ticker, new BigDecimal(price));
                } catch (NumberFormatException e) {
                    priceMap.put(ticker, BigDecimal.ZERO);
                }
            } else {
                priceMap.put(ticker, BigDecimal.ZERO);
            }
        }
        return priceMap;
    }
}
