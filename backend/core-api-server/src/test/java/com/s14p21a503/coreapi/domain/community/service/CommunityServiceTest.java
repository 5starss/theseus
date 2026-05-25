package com.s14p21a503.coreapi.domain.community.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostUpdateRequestDto;
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
}
