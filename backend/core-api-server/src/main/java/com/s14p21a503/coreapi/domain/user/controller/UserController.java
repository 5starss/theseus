package com.s14p21a503.coreapi.domain.user.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.user.dto.UserProfileResponseDto;
import com.s14p21a503.coreapi.domain.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

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
}
