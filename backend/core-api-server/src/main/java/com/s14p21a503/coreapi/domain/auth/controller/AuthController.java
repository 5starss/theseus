package com.s14p21a503.coreapi.domain.auth.controller;

import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.auth.dto.request.SignupRequestDto;
import com.s14p21a503.coreapi.domain.auth.dto.response.SignupResponseDto;
import com.s14p21a503.coreapi.domain.auth.service.AuthService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final AuthService authService;

    @PostMapping("/signup")
    public ResponseEntity<ApiResponse<SignupResponseDto>> signUp(@RequestBody SignupRequestDto dto) {

        Long userId = authService.signUp(dto);
        SignupResponseDto response = new SignupResponseDto(userId);

        return ApiResponse.onSuccess(SuccessCode.CREATED, response);
    }
}
