package com.s14p21a503.coreapi.domain.auth.controller;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.auth.dto.request.LoginRequestDto;
import com.s14p21a503.coreapi.domain.auth.dto.request.SignupRequestDto;
import com.s14p21a503.coreapi.domain.auth.dto.response.SignupResponseDto;
import com.s14p21a503.coreapi.domain.auth.dto.response.TokenResponseDto;
import com.s14p21a503.coreapi.domain.auth.service.AuthService;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.time.Duration;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final AuthService authService;
    @Value("${auth.refresh-cookie.name:refresh_token}")
    private String refreshCookieName;
    @Value("${auth.refresh-cookie.path:/api/v1/core/auth}")
    private String refreshCookiePath;
    @Value("${auth.refresh-cookie.domain:}")
    private String refreshCookieDomain;
    @Value("${auth.refresh-cookie.secure:true}")
    private boolean refreshCookieSecure;
    @Value("${auth.refresh-cookie.same-site:Lax}")
    private String refreshCookieSameSite;
    @Value("${auth.refresh-cookie.max-age-millis:${JWT_REFRESH_EXPIRATION:1209600000}}")
    private long refreshCookieMaxAgeMillis;
    @Value("${auth.csrf.enforce-origin-check:false}")
    private boolean enforceOriginCheck;
    @Value("${auth.csrf.allowed-origins:}")
    private String allowedOriginsRaw;

    @PostMapping("/signup")
    public ResponseEntity<ApiResponse<SignupResponseDto>> signUp(@RequestBody SignupRequestDto dto) {

        Long userId = authService.signUp(dto);
        SignupResponseDto response = new SignupResponseDto(userId);

        return ApiResponse.onSuccess(SuccessCode.CREATED, response);
    }

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<TokenResponseDto>> login(@RequestBody LoginRequestDto dto,
                                                               HttpServletResponse response) {
        AuthService.TokenPair tokenPair = authService.login(dto);
        addRefreshTokenCookie(response, tokenPair.refreshToken());
        return ApiResponse.onSuccess(SuccessCode.OK, toAccessTokenResponse(tokenPair));
    }

    @PostMapping("/refresh")
    public ResponseEntity<ApiResponse<TokenResponseDto>> refresh(HttpServletRequest request,
                                                                 HttpServletResponse response) {
        validateCsrfOrigin(request);

        String refreshToken = extractRefreshToken(request);
        AuthService.TokenPair tokenPair = authService.refresh(refreshToken);
        addRefreshTokenCookie(response, tokenPair.refreshToken());

        return ApiResponse.onSuccess(SuccessCode.OK, toAccessTokenResponse(tokenPair));
    }

    @PostMapping("/logout")
    public ResponseEntity<ApiResponse<Void>> logout(@RequestHeader("X-USER-ID") Long userId,
                                                    HttpServletRequest request,
                                                    HttpServletResponse response) {
        validateCsrfOrigin(request);
        authService.logout(userId);
        clearRefreshTokenCookie(response);
        return ApiResponse.onSuccess(SuccessCode.OK);
    }

    private TokenResponseDto toAccessTokenResponse(AuthService.TokenPair tokenPair) {
        return TokenResponseDto.builder()
                .userId(tokenPair.userId())
                .tokenType(tokenPair.tokenType())
                .accessToken(tokenPair.accessToken())
                .nickname(tokenPair.nickname())
                .accessTokenExpiresAt(tokenPair.accessTokenExpiresAt())
                .build();
    }

    private String extractRefreshToken(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) {
            throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
        }

        for (Cookie cookie : cookies) {
            if (refreshCookieName.equals(cookie.getName()) && StringUtils.hasText(cookie.getValue())) {
                return cookie.getValue();
            }
        }

        throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
    }

    private void addRefreshTokenCookie(HttpServletResponse response, String refreshToken) {
        ResponseCookie.ResponseCookieBuilder cookieBuilder = ResponseCookie.from(refreshCookieName, refreshToken)
                .httpOnly(true)
                .secure(refreshCookieSecure)
                .sameSite(refreshCookieSameSite)
                .path(refreshCookiePath)
                .maxAge(Duration.ofMillis(refreshCookieMaxAgeMillis));

        if (StringUtils.hasText(refreshCookieDomain)) {
            cookieBuilder.domain(refreshCookieDomain);
        }

        response.addHeader(HttpHeaders.SET_COOKIE, cookieBuilder.build().toString());
    }

    private void clearRefreshTokenCookie(HttpServletResponse response) {
        ResponseCookie.ResponseCookieBuilder cookieBuilder = ResponseCookie.from(refreshCookieName, "")
                .httpOnly(true)
                .secure(refreshCookieSecure)
                .sameSite(refreshCookieSameSite)
                .path(refreshCookiePath)
                .maxAge(Duration.ZERO);

        if (StringUtils.hasText(refreshCookieDomain)) {
            cookieBuilder.domain(refreshCookieDomain);
        }

        response.addHeader(HttpHeaders.SET_COOKIE, cookieBuilder.build().toString());
    }

    private void validateCsrfOrigin(HttpServletRequest request) {
        if (!enforceOriginCheck) {
            return;
        }

        Set<String> allowedOrigins = Arrays.stream(allowedOriginsRaw.split(","))
                .map(String::trim)
                .filter(StringUtils::hasText)
                .collect(Collectors.toSet());

        if (allowedOrigins.isEmpty()) {
            throw new CustomException(ErrorCode.ACCESS_DENIED);
        }

        String origin = request.getHeader(HttpHeaders.ORIGIN);
        if (!StringUtils.hasText(origin) || !allowedOrigins.contains(origin)) {
            throw new CustomException(ErrorCode.ACCESS_DENIED);
        }
    }
}
