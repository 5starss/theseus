package com.s14p21a503.coreapi.domain.community.dto;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class CommunityCommentResponseDto {

    private Long commentId;
    private Long postId;
    private Long authorId;
    private String authorNickname;
    private String content;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private boolean isShareholder;
}
