package com.s14p21a503.coreapi.domain.community.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.community.dto.CommunityCommentUpdateRequestDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostUpdateRequestDto;
import com.s14p21a503.coreapi.domain.community.entity.CommunityComment;
import com.s14p21a503.coreapi.domain.community.entity.CommunityPost;
import com.s14p21a503.coreapi.domain.community.repository.CommunityCommentRepository;
import com.s14p21a503.coreapi.domain.community.repository.CommunityPostRepository;
import com.s14p21a503.coreapi.domain.stock.repository.StockRepository;
import com.s14p21a503.coreapi.domain.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CommunityServiceTest {

    @Mock
    private CommunityPostRepository communityPostRepository;

    @Mock
    private CommunityCommentRepository communityCommentRepository;

    @Mock
    private StockRepository stockRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private ShareholderBadgeService shareholderBadgeService;

    @Mock
    private CommunityLikeService communityLikeService;

    @InjectMocks
    private CommunityService communityService;

    @Test
    void updatePostThrowsWhenRequesterIsNotAuthor() {
        CommunityPost post = CommunityPost.builder()
                .userId(1L)
                .ticker("005930")
                .title("title")
                .content("content")
                .build();
        ReflectionTestUtils.setField(post, "id", 10L);

        CommunityPostUpdateRequestDto requestDto = new CommunityPostUpdateRequestDto();
        ReflectionTestUtils.setField(requestDto, "title", "updated title");
        ReflectionTestUtils.setField(requestDto, "content", "updated content");

        when(communityPostRepository.findById(10L)).thenReturn(Optional.of(post));

        CustomException exception = assertThrows(
                CustomException.class,
                () -> communityService.updatePost(2L, 10L, requestDto)
        );

        assertEquals(ErrorCode.ACCESS_DENIED, exception.getErrorCode());
    }

    @Test
    void deletePostThrowsWhenRequesterIsNotAuthor() {
        CommunityPost post = CommunityPost.builder()
                .userId(1L)
                .ticker("005930")
                .title("title")
                .content("content")
                .build();
        ReflectionTestUtils.setField(post, "id", 10L);

        when(communityPostRepository.findById(10L)).thenReturn(Optional.of(post));

        CustomException exception = assertThrows(
                CustomException.class,
                () -> communityService.deletePost(2L, 10L)
        );

        assertEquals(ErrorCode.ACCESS_DENIED, exception.getErrorCode());
    }

    @Test
    void updateCommentThrowsWhenRequesterIsNotAuthor() {
        CommunityComment comment = CommunityComment.builder()
                .postId(10L)
                .userId(1L)
                .content("content")
                .build();
        ReflectionTestUtils.setField(comment, "id", 20L);

        CommunityCommentUpdateRequestDto requestDto = new CommunityCommentUpdateRequestDto();
        ReflectionTestUtils.setField(requestDto, "content", "updated content");

        when(communityCommentRepository.findById(20L)).thenReturn(Optional.of(comment));

        CustomException exception = assertThrows(
                CustomException.class,
                () -> communityService.updateComment(2L, 20L, requestDto)
        );

        assertEquals(ErrorCode.ACCESS_DENIED, exception.getErrorCode());
    }

    @Test
    void deleteCommentThrowsWhenRequesterIsNotAuthor() {
        CommunityComment comment = CommunityComment.builder()
                .postId(10L)
                .userId(1L)
                .content("content")
                .build();
        ReflectionTestUtils.setField(comment, "id", 20L);

        when(communityCommentRepository.findById(20L)).thenReturn(Optional.of(comment));

        CustomException exception = assertThrows(
                CustomException.class,
                () -> communityService.deleteComment(2L, 20L)
        );

        assertEquals(ErrorCode.ACCESS_DENIED, exception.getErrorCode());
    }
}
