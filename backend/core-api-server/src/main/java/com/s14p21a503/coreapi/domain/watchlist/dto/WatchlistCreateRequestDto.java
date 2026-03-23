package com.s14p21a503.coreapi.domain.watchlist.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class WatchlistCreateRequestDto {

    @NotBlank(message = "종목 코드는 필수입니다.")
    private String ticker;
}
