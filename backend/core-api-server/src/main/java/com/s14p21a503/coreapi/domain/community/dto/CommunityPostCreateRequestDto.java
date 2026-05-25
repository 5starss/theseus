package com.s14p21a503.coreapi.domain.community.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class CommunityPostCreateRequestDto {

    private String stockId;
    private String stockCode;
    private String title;
    private String content;
}
