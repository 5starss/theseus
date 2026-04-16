package com.s14p21a503.coreapi.domain.auth.dto.request;

import com.s14p21a503.coreapi.domain.user.entity.InvestmentStyle;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class SignupRequestDto {

    private String email;
    private String password;
    private String nickname;
    private InvestmentStyle investmentStyle;

}
