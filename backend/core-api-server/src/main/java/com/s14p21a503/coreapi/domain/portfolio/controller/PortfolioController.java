package com.s14p21a503.coreapi.domain.portfolio.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.portfolio.dto.PortfolioSummaryResponseDto;
import com.s14p21a503.coreapi.domain.portfolio.service.PortfolioService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/portfolio")
public class PortfolioController {

    private final PortfolioService portfolioService;

    @GetMapping("/me/summary")
    public ResponseEntity<ApiResponse<PortfolioSummaryResponseDto>> getMyPortfolioSummary(
            @RequestHeader("X-User-Id") Long userId
    ) {
        return ApiResponse.onSuccess(SuccessCode.OK, portfolioService.getMyPortfolioSummary(userId));
    }
}
