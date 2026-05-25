package com.s14p21a503.coreapi.domain.community.dto;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class CommunityLikeToggleResponseDto {

    private boolean liked;
    private long likeCount;
}
