package com.s14p21a503.coreapi.domain.auth.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.auth.dto.request.LoginRequestDto;
import com.s14p21a503.coreapi.domain.auth.dto.request.SignupRequestDto;
import com.s14p21a503.coreapi.domain.auth.token.JwtProvider;
import com.s14p21a503.coreapi.domain.user.entity.User;
import com.s14p21a503.coreapi.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class AuthService {

    private static final String REFRESH_TOKEN_PREFIX = "RT:";

    private final UserRepository userRepository;
    private final BCryptPasswordEncoder passwordEncoder;
    private final JwtProvider jwtProvider;
    private final RedisTemplate<String, Object> redisTemplate;

    @Transactional
    public Long signUp(SignupRequestDto dto) {

        // 1) 1차 중복 체크
        if (userRepository.existsByEmail(dto.getEmail())) {
            throw new CustomException(ErrorCode.DUPLICATE_EMAIL);
        }

        // 2) 비밀번호 암호화
        String encodedPassword = passwordEncoder.encode(dto.getPassword());

        User user = User.builder()
                .email(dto.getEmail())
                .password(encodedPassword)
                .nickname(dto.getNickname())
                .investmentStyle(dto.getInvestmentStyle())
                .build();


        // 4) 저장 (race condition 대비: UNIQUE 제약 예외 catch)
        try {
            return userRepository.save(user).getId();
        } catch (DataIntegrityViolationException e) {
            throw new CustomException(ErrorCode.DUPLICATE_EMAIL);
        }
    }

    @Transactional
    public TokenPair login(LoginRequestDto dto) {
        User user = userRepository.findByEmail(dto.getEmail())
                .orElseThrow(() -> new CustomException(ErrorCode.LOGIN_FAILED));

        if (!passwordEncoder.matches(dto.getPassword(), user.getPassword())) {
            throw new CustomException(ErrorCode.LOGIN_FAILED);
        }

        return issueTokenPair(user.getId());
    }

    @Transactional
    public TokenPair refresh(String refreshToken) {

        if (!jwtProvider.validateToken(refreshToken)) {
            throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
        }

        Long userId;
        try {
            userId = jwtProvider.getUserIdFromToken(refreshToken);
        } catch (CustomException e) {
            throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
        }

        String redisToken = getStoredRefreshToken(userId);
        if (redisToken == null || !redisToken.equals(refreshToken)) {
            throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
        }

        if (!userRepository.existsById(userId)) {
            throw new CustomException(ErrorCode.INVALID_REFRESH_TOKEN);
        }

        return issueTokenPair(userId);
    }

    @Transactional
    public void logout(Long userId) {
        redisTemplate.delete(refreshTokenKey(userId));
    }

    private TokenPair issueTokenPair(Long userId) {
        String accessToken = jwtProvider.createAccessToken(userId);
        String refreshToken = jwtProvider.createRefreshToken(userId);

        saveRefreshToken(userId, refreshToken);

        LocalDateTime now = LocalDateTime.now();

        return new TokenPair(
                "Bearer",
                accessToken,
                refreshToken,
                now.plus(Duration.ofMillis(jwtProvider.getAccessExpiration())),
                now.plus(Duration.ofMillis(jwtProvider.getRefreshExpiration()))
        );
    }

    private void saveRefreshToken(Long userId, String refreshToken) {
        redisTemplate.opsForValue().set(
                refreshTokenKey(userId),
                refreshToken,
                Duration.ofMillis(jwtProvider.getRefreshExpiration())
        );
    }

    private String getStoredRefreshToken(Long userId) {
        Object value = redisTemplate.opsForValue().get(refreshTokenKey(userId));
        return value == null ? null : String.valueOf(value);
    }

    private String refreshTokenKey(Long userId) {
        return REFRESH_TOKEN_PREFIX + userId;
    }

    public record TokenPair(
            String tokenType,
            String accessToken,
            String refreshToken,
            LocalDateTime accessTokenExpiresAt,
            LocalDateTime refreshTokenExpiresAt
    ) {
    }
}
