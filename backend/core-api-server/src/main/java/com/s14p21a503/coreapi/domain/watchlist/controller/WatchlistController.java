package com.s14p21a503.coreapi.domain.watchlist.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.watchlist.dto.WatchlistCreateRequestDto;
import com.s14p21a503.coreapi.domain.watchlist.dto.WatchlistResponseDto;
import com.s14p21a503.coreapi.domain.watchlist.service.WatchlistService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Tag(name = "Watchlist", description = "관심종목 API")
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/watchlists")
public class WatchlistController {

    private final WatchlistService watchlistService;

    @Operation(summary = "관심종목 등록", description = "사용자의 관심종목을 등록합니다.")
    @PostMapping
    public ResponseEntity<ApiResponse<Void>> createWatchlist(
            @RequestHeader("X-User-Id") Long userId,
            @Valid @RequestBody WatchlistCreateRequestDto requestDto) {
        watchlistService.createWatchlist(userId, requestDto);
        return ApiResponse.onSuccess(SuccessCode.CREATED);
    }

    @Operation(summary = "관심종목 삭제", description = "사용자의 관심종목을 삭제합니다.")
    @DeleteMapping("/{ticker}")
    public ResponseEntity<ApiResponse<Void>> deleteWatchlist(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable String ticker) {
        watchlistService.deleteWatchlist(userId, ticker);
        return ApiResponse.onSuccess(SuccessCode.OK);
    }

    @Operation(summary = "관심종목 목록 조회", description = "사용자의 관심종목 목록과 보유 여부를 조회합니다.")
    @GetMapping
    public ResponseEntity<ApiResponse<List<WatchlistResponseDto>>> getWatchlists(
            @RequestHeader("X-User-Id") Long userId) {
        return ApiResponse.onSuccess(SuccessCode.OK, watchlistService.getWatchlists(userId));
    }
}
