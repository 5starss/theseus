package com.s14p21a503.coreapi.domain.community.controller;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.ApiResponse;
import com.s14p21a503.coreapi.common.response.PageResponseDto;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.common.response.status.SuccessCode;
import com.s14p21a503.coreapi.domain.community.dto.CommunityCommentCreateRequestDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityCommentResponseDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityCommentUpdateRequestDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityLikeToggleResponseDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostCreateRequestDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostDetailResponseDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostSortType;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostSummaryResponseDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostUpdateRequestDto;
import com.s14p21a503.coreapi.domain.community.service.CommunityLikeService;
import com.s14p21a503.coreapi.domain.community.service.CommunityService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/community")
public class CommunityController {

    private final CommunityService communityService;
    private final CommunityLikeService communityLikeService;

    @GetMapping("/posts")
    public ResponseEntity<ApiResponse<PageResponseDto<CommunityPostSummaryResponseDto>>> getPosts(
            @RequestHeader(value = "X-User-Id", required = false) Long userId,
            @RequestParam(required = false) String stockId,
            @RequestParam(required = false) String stockCode,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "latest") String sort
    ) {
        validatePageRequest(page, size);
        Pageable pageable = PageRequest.of(page, size);
        return ApiResponse.onSuccess(
                SuccessCode.OK,
                communityService.getPosts(userId, stockId, stockCode, CommunityPostSortType.from(sort), pageable)
        );
    }

    @GetMapping("/posts/{postId}")
    public ResponseEntity<ApiResponse<CommunityPostDetailResponseDto>> getPostDetail(
            @RequestHeader(value = "X-User-Id", required = false) Long userId,
            @PathVariable Long postId
    ) {
        return ApiResponse.onSuccess(SuccessCode.OK, communityService.getPostDetail(userId, postId));
    }

    @PostMapping("/posts")
    public ResponseEntity<ApiResponse<CommunityPostDetailResponseDto>> createPost(
            @RequestHeader("X-User-Id") Long userId,
            @RequestBody CommunityPostCreateRequestDto requestDto
    ) {
        return ApiResponse.onSuccess(SuccessCode.CREATED, communityService.createPost(userId, requestDto));
    }

    @PutMapping("/posts/{postId}")
    public ResponseEntity<ApiResponse<CommunityPostDetailResponseDto>> updatePost(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long postId,
            @RequestBody CommunityPostUpdateRequestDto requestDto
    ) {
        return ApiResponse.onSuccess(SuccessCode.OK, communityService.updatePost(userId, postId, requestDto));
    }

    @DeleteMapping("/posts/{postId}")
    public ResponseEntity<ApiResponse<Void>> deletePost(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long postId
    ) {
        communityService.deletePost(userId, postId);
        return ApiResponse.onSuccess(SuccessCode.OK);
    }

    @PostMapping("/posts/{postId}/views")
    public ResponseEntity<ApiResponse<Void>> increaseViewCount(@PathVariable Long postId) {
        communityService.increaseViewCount(postId);
        return ApiResponse.onSuccess(SuccessCode.OK);
    }

    @GetMapping("/posts/{postId}/comments")
    public ResponseEntity<ApiResponse<List<CommunityCommentResponseDto>>> getComments(
            @RequestHeader(value = "X-User-Id", required = false) Long userId,
            @PathVariable Long postId
    ) {
        return ApiResponse.onSuccess(SuccessCode.OK, communityService.getComments(userId, postId));
    }

    @PostMapping("/posts/{postId}/comments")
    public ResponseEntity<ApiResponse<CommunityCommentResponseDto>> createComment(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long postId,
            @RequestBody CommunityCommentCreateRequestDto requestDto
    ) {
        return ApiResponse.onSuccess(SuccessCode.CREATED, communityService.createComment(userId, postId, requestDto));
    }

    @PutMapping("/comments/{commentId}")
    public ResponseEntity<ApiResponse<CommunityCommentResponseDto>> updateComment(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long commentId,
            @RequestBody CommunityCommentUpdateRequestDto requestDto
    ) {
        return ApiResponse.onSuccess(SuccessCode.OK, communityService.updateComment(userId, commentId, requestDto));
    }

    @DeleteMapping("/comments/{commentId}")
    public ResponseEntity<ApiResponse<Void>> deleteComment(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long commentId
    ) {
        communityService.deleteComment(userId, commentId);
        return ApiResponse.onSuccess(SuccessCode.OK);
    }

    @PostMapping("/posts/{postId}/likes")
    public ResponseEntity<ApiResponse<CommunityLikeToggleResponseDto>> togglePostLike(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long postId
    ) {
        return ApiResponse.onSuccess(SuccessCode.OK, communityLikeService.togglePostLike(userId, postId));
    }

    @PostMapping("/comments/{commentId}/likes")
    public ResponseEntity<ApiResponse<CommunityLikeToggleResponseDto>> toggleCommentLike(
            @RequestHeader("X-User-Id") Long userId,
            @PathVariable Long commentId
    ) {
        return ApiResponse.onSuccess(SuccessCode.OK, communityLikeService.toggleCommentLike(userId, commentId));
    }

    private void validatePageRequest(int page, int size) {
        if (page < 0 || size <= 0) {
            throw new CustomException(ErrorCode.INVALID_INPUT_VALUE);
        }
    }
}
