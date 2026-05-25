package com.s14p21a503.coreapi.domain.community.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class CommunityPostSummaryResponseDto {

    private Long postId;
    private String stockCode;
    private String stockName;
    private String title;
    private Long authorId;
    private String authorNickname;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private long viewCount;
    private long commentCount;
    private long likeCount;
    private Boolean likedByMe;
    @JsonProperty("isShareholder")
    private Boolean isShareholder;
}
