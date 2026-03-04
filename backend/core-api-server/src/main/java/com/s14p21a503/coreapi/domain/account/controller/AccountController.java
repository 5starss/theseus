package com.s14p21a503.coreapi.domain.account.controller;


import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.account.dto.AccountBalanceResponseDto;
import com.s14p21a503.coreapi.domain.account.service.AccountService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/accounts")
public class AccountController {
    private final AccountService accountService;

    @GetMapping("/balance")
    public ResponseEntity<ApiResponse<AccountBalanceResponseDto>> getBalance(
            @RequestHeader(value = "X-User-Id") Long userId) {
        return ApiResponse.onSuccess(SuccessCode.OK, accountService.getBalance(userId));
    }
}
