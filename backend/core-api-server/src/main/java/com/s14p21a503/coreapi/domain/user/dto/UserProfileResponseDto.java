package com.s14p21a503.coreapi.domain.user.dto;

import com.s14p21a503.coreapi.domain.user.entity.InvestmentStyle;
import com.s14p21a503.coreapi.domain.user.entity.User;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class UserProfileResponseDto {
    private Long userId;
    private String email;
    private String nickname;
    private InvestmentStyle investmentStyle;

    public static UserProfileResponseDto from(User user) {
        return UserProfileResponseDto.builder()
                .userId(user.getId())
                .email(user.getEmail())
                .nickname(user.getNickname())
                .investmentStyle(user.getInvestmentStyle())
                .build();
    }
}
