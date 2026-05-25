package com.s14p21a503.coreapi.domain.community.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class CommunityPostDetailResponseDto {

    private Long postId;
    private String stockCode;
    private String stockName;
    private String title;
    private String content;
    private Long authorId;
    private String authorNickname;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private long viewCount;
    private long commentCount;
    @JsonProperty("isShareholder")
    private Boolean isShareholder;
}
