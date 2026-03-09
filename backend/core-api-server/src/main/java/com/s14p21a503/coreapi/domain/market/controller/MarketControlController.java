package com.s14p21a503.coreapi.domain.market.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.market.service.MarketService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 전역 시장 제어 컨트롤러 (관리자용).
 * 시장 일시 정지(HALT), 재개(RESUME), 수동 개장/종료 등을 처리합니다.
 */
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/admin/market")
public class MarketControlController {

    private final MarketService marketService;

    @PostMapping("/open")
    public ResponseEntity<ApiResponse<Void>> openMarket() {
        marketService.openMarket();
        return ApiResponse.onSuccess(SuccessCode.OK, null);
    }

    @PostMapping("/close")
    public ResponseEntity<ApiResponse<Void>> closeMarket() {
        marketService.closeMarket();
        return ApiResponse.onSuccess(SuccessCode.OK, null);
    }

    @PostMapping("/halt")
    public ResponseEntity<ApiResponse<Void>> haltMarket() {
        marketService.haltMarket();
        return ApiResponse.onSuccess(SuccessCode.OK, null);
    }

    @PostMapping("/resume")
    public ResponseEntity<ApiResponse<Void>> resumeMarket() {
        marketService.resumeMarket();
        return ApiResponse.onSuccess(SuccessCode.OK, null);
    }

    @PostMapping("/holidays/sync")
    public ResponseEntity<ApiResponse<Void>> syncHolidays() {
        marketService.syncHolidays();
        return ApiResponse.onSuccess(SuccessCode.OK, null);
    }
}
