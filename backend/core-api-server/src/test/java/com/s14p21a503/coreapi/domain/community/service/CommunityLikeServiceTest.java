package com.s14p21a503.coreapi.domain.community.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.community.dto.CommunityLikeToggleResponseDto;
import com.s14p21a503.coreapi.domain.community.entity.CommunityCommentLike;
import com.s14p21a503.coreapi.domain.community.entity.CommunityPostLike;
import com.s14p21a503.coreapi.domain.community.repository.CommunityCommentLikeRepository;
import com.s14p21a503.coreapi.domain.community.repository.CommunityCommentRepository;
import com.s14p21a503.coreapi.domain.community.repository.CommunityPostLikeRepository;
import com.s14p21a503.coreapi.domain.community.repository.CommunityPostRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CommunityLikeServiceTest {

    @Mock
    private CommunityPostRepository communityPostRepository;

    @Mock
    private CommunityCommentRepository communityCommentRepository;

    @Mock
    private CommunityPostLikeRepository communityPostLikeRepository;

    @Mock
    private CommunityCommentLikeRepository communityCommentLikeRepository;

    @InjectMocks
    private CommunityLikeService communityLikeService;

    @Test
    void togglePostLikeAddsLikeWhenNotExists() {
        when(communityPostRepository.existsById(10L)).thenReturn(true);
        when(communityPostLikeRepository.findByCommunityPostIdAndUserId(10L, 1L)).thenReturn(Optional.empty());
        when(communityPostLikeRepository.countByCommunityPostId(10L)).thenReturn(1L);

        CommunityLikeToggleResponseDto response = communityLikeService.togglePostLike(1L, 10L);

        assertTrue(response.isLiked());
        assertEquals(1L, response.getLikeCount());
        verify(communityPostLikeRepository).save(any(CommunityPostLike.class));
    }

    @Test
    void togglePostLikeRemovesLikeWhenExists() {
        CommunityPostLike existingLike = CommunityPostLike.builder()
                .communityPostId(10L)
                .userId(1L)
                .build();

        when(communityPostRepository.existsById(10L)).thenReturn(true);
        when(communityPostLikeRepository.findByCommunityPostIdAndUserId(10L, 1L)).thenReturn(Optional.of(existingLike));
        when(communityPostLikeRepository.countByCommunityPostId(10L)).thenReturn(0L);

        CommunityLikeToggleResponseDto response = communityLikeService.togglePostLike(1L, 10L);

        assertFalse(response.isLiked());
        assertEquals(0L, response.getLikeCount());
        verify(communityPostLikeRepository).delete(existingLike);
    }

    @Test
    void toggleCommentLikeAddsLikeWhenNotExists() {
        when(communityCommentRepository.existsById(20L)).thenReturn(true);
        when(communityCommentLikeRepository.findByCommunityCommentIdAndUserId(20L, 1L)).thenReturn(Optional.empty());
        when(communityCommentLikeRepository.countByCommunityCommentId(20L)).thenReturn(1L);

        CommunityLikeToggleResponseDto response = communityLikeService.toggleCommentLike(1L, 20L);

        assertTrue(response.isLiked());
        assertEquals(1L, response.getLikeCount());
        verify(communityCommentLikeRepository).save(any(CommunityCommentLike.class));
    }

    @Test
    void toggleCommentLikeThrowsWhenCommentNotFound() {
        when(communityCommentRepository.existsById(20L)).thenReturn(false);

        CustomException exception = assertThrows(
                CustomException.class,
                () -> communityLikeService.toggleCommentLike(1L, 20L)
        );

        assertEquals(ErrorCode.COMMUNITY_COMMENT_NOT_FOUND, exception.getErrorCode());
    }
}
