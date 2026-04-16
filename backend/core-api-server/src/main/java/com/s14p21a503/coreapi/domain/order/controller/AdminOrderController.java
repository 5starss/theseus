package com.s14p21a503.coreapi.domain.order.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.order.dto.AdminForceExecuteDto;
import com.s14p21a503.coreapi.domain.order.service.AdminOrderService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/admin/orders")
public class AdminOrderController {

    private final AdminOrderService adminOrderService;

    // 강제 취소 (매칭 엔진 상태와 무관하게 DB 강제 취소 반영)
    @PostMapping("/{orderId}/force-cancel")
    public ResponseEntity<ApiResponse<Void>> forceCancelOrder(
            @RequestHeader(value = "X-User-Id", required = false) Long adminId,
            @PathVariable Long orderId) {
        // 실제 운영 시에는 adminId 권한 체크 추가 필요
        adminOrderService.forceCancelOrder(orderId);
        return ApiResponse.onSuccess(SuccessCode.OK, null);
    }

    // 강제 체결 (매칭 엔진 로직을 우회하여 DB 강제 체결 반영)
    @PostMapping("/{orderId}/force-execute")
    public ResponseEntity<ApiResponse<Void>> forceExecuteOrder(
            @RequestHeader(value = "X-User-Id", required = false) Long adminId,
            @PathVariable Long orderId,
            @RequestBody AdminForceExecuteDto requestDto) {
        // 실제 운영 시에는 adminId 권한 체크 추가 필요
        adminOrderService.forceExecuteOrder(orderId, requestDto);
        return ApiResponse.onSuccess(SuccessCode.OK, null);
    }
}
