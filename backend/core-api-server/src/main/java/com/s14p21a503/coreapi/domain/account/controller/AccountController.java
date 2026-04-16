package com.s14p21a503.coreapi.domain.account.controller;


import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.account.dto.AccountBalanceResponseDto;
import com.s14p21a503.coreapi.domain.account.dto.AccountHistoryResponseDto;
import com.s14p21a503.coreapi.domain.account.dto.AccountSummaryResponseDto;
import com.s14p21a503.coreapi.domain.account.dto.TransferRequestDto;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.account.service.AccountService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/accounts")
public class AccountController {
    private final AccountService accountService;

    @GetMapping("/balance")
    public ResponseEntity<ApiResponse<AccountBalanceResponseDto>> getBalance(
            @RequestHeader(value = "X-User-Id") Long userId,
            @RequestParam(name = "account_type", defaultValue = "USER") AccountType accountType) {
        return ApiResponse.onSuccess(SuccessCode.OK, accountService.getBalance(userId, accountType));
    }

    @GetMapping("/summary")
    public ResponseEntity<ApiResponse<AccountSummaryResponseDto>> getSummary(
            @RequestHeader(value = "X-User-Id") Long userId,
            @RequestParam(name = "account_type", defaultValue = "USER") AccountType accountType) {
        return ApiResponse.onSuccess(SuccessCode.OK, accountService.getSummary(userId, accountType));
    }

    @GetMapping("/history")
    public ResponseEntity<ApiResponse<AccountHistoryResponseDto>> getHistory(
            @RequestHeader(value = "X-User-Id") Long userId,
            @RequestParam(name = "account_type", defaultValue = "USER") AccountType accountType,
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) Integer month,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.onSuccess(SuccessCode.OK,
                accountService.getHistories(userId, accountType, year, month, PageRequest.of(page, size)));
    }

    @PostMapping("/transfer")
    public ResponseEntity<ApiResponse<Void>> transfer(
            @RequestHeader(value = "X-User-Id") Long userId,
            @RequestBody TransferRequestDto requestDto) {
        accountService.transfer(userId, requestDto);
        return ApiResponse.onSuccess(SuccessCode.OK);
    }
}
