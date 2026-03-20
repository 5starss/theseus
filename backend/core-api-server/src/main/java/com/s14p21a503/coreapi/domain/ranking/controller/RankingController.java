package com.s14p21a503.coreapi.domain.ranking.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.ranking.dto.RankingResponseDto;
import com.s14p21a503.coreapi.domain.ranking.service.RankingService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/rankings")
public class RankingController {

    private final RankingService rankingService;

    /**
     * 일간 랭킹 목록 및 내 순위를 조회합니다.
     * @param userId 헤더에서 전달받은 사용자 ID
     * @param page 페이지 번호 (0부터 시작)
     * @param size 페이지 크기
     */
    @GetMapping
    public ResponseEntity<ApiResponse<RankingResponseDto>> getRankings(
            @RequestHeader(value = "X-User-Id", required = false) Long userId,
            @RequestParam(required = false) String nickname,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size) {
        
        RankingResponseDto response = rankingService.getRankings(userId, nickname, PageRequest.of(page, size));
        return ApiResponse.onSuccess(SuccessCode.OK, response);
    }

    /**
     * 수동으로 랭킹 스냅샷을 생성하는 관리자용 API
     * 테스트 편의를 위해 제공합니다.
     */
    @PostMapping("/snapshot")
    public ResponseEntity<ApiResponse<Void>> createSnapshot() {
        rankingService.createDailySnapshot();
        return ApiResponse.onSuccess(SuccessCode.OK);
    }
}
