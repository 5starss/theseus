package com.s14p21a503.coreapi.domain.auth.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.auth.dto.request.SignupRequestDto;
import com.s14p21a503.coreapi.domain.user.entity.User;
import com.s14p21a503.coreapi.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final BCryptPasswordEncoder passwordEncoder;

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
}
