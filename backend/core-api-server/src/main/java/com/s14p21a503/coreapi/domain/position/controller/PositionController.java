package com.s14p21a503.coreapi.domain.position.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.position.dto.PositionResponseDto;
import com.s14p21a503.coreapi.domain.position.service.PositionService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/positions")
public class PositionController {

    private final PositionService positionService;

    @GetMapping
    public ResponseEntity<ApiResponse<List<PositionResponseDto>>> getPositions(
            @RequestHeader("X-User-Id") Long userId,
            @RequestParam(required = false) AccountType accountType) {
        return ApiResponse.onSuccess(SuccessCode.OK, positionService.getPositions(userId, accountType));
    }
}
