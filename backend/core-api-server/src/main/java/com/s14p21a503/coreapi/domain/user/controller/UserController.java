package com.s14p21a503.coreapi.domain.user.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.user.dto.UserProfileResponseDto;
import com.s14p21a503.coreapi.domain.user.dto.InvestmentStyleUpdateRequestDto;
import com.s14p21a503.coreapi.domain.user.service.UserService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/users")
public class UserController {

    private final UserService userService;

    @GetMapping("/me")
    public ResponseEntity<ApiResponse<UserProfileResponseDto>> getMyProfile(
            @RequestHeader(value = "X-User-Id") Long userId) {
        return ApiResponse.onSuccess(SuccessCode.OK, userService.getProfile(userId));
    }

    @PatchMapping("/me/investment-style")
    public ResponseEntity<ApiResponse<UserProfileResponseDto>> updateInvestmentStyle(
            @RequestHeader(value = "X-User-Id") Long userId,
            @Valid @RequestBody InvestmentStyleUpdateRequestDto dto) {
        return ApiResponse.onSuccess(SuccessCode.OK, userService.updateInvestmentStyle(userId, dto));
    }
}
