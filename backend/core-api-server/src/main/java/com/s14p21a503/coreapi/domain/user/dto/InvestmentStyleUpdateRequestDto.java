package com.s14p21a503.coreapi.domain.user.dto;

import com.s14p21a503.coreapi.domain.user.entity.InvestmentStyle;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class InvestmentStyleUpdateRequestDto {
    @NotNull(message = "투자 성향은 필수입니다.")
    private InvestmentStyle investmentStyle;
}
