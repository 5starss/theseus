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
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CommunityLikeService {

    private final CommunityPostRepository communityPostRepository;
    private final CommunityCommentRepository communityCommentRepository;
    private final CommunityPostLikeRepository communityPostLikeRepository;
    private final CommunityCommentLikeRepository communityCommentLikeRepository;

    @Transactional
    public CommunityLikeToggleResponseDto togglePostLike(Long userId, Long postId) {
        validatePostExists(postId);

        boolean liked = communityPostLikeRepository.findByCommunityPostIdAndUserId(postId, userId)
                .map(existingLike -> {
                    communityPostLikeRepository.delete(existingLike);
                    return false;
                })
                .orElseGet(() -> {
                    communityPostLikeRepository.save(
                            CommunityPostLike.builder()
                                    .communityPostId(postId)
                                    .userId(userId)
                                    .build()
                    );
                    return true;
                });

        return CommunityLikeToggleResponseDto.builder()
                .liked(liked)
                .likeCount(communityPostLikeRepository.countByCommunityPostId(postId))
                .build();
    }

    @Transactional
    public CommunityLikeToggleResponseDto toggleCommentLike(Long userId, Long commentId) {
        validateCommentExists(commentId);

        boolean liked = communityCommentLikeRepository.findByCommunityCommentIdAndUserId(commentId, userId)
                .map(existingLike -> {
                    communityCommentLikeRepository.delete(existingLike);
                    return false;
                })
                .orElseGet(() -> {
                    communityCommentLikeRepository.save(
                            CommunityCommentLike.builder()
                                    .communityCommentId(commentId)
                                    .userId(userId)
                                    .build()
                    );
                    return true;
                });

        return CommunityLikeToggleResponseDto.builder()
                .liked(liked)
                .likeCount(communityCommentLikeRepository.countByCommunityCommentId(commentId))
                .build();
    }

    @Transactional(readOnly = true)
    public Map<Long, Long> getPostLikeCountMap(Collection<Long> postIds) {
        if (postIds == null || postIds.isEmpty()) {
            return Collections.emptyMap();
        }

        return communityPostLikeRepository.countByCommunityPostIds(postIds).stream()
                .collect(Collectors.toMap(
                        row -> (Long) row[0],
                        row -> (Long) row[1]
                ));
    }

    @Transactional(readOnly = true)
    public Map<Long, Long> getCommentLikeCountMap(Collection<Long> commentIds) {
        if (commentIds == null || commentIds.isEmpty()) {
            return Collections.emptyMap();
        }

        return communityCommentLikeRepository.countByCommunityCommentIds(commentIds).stream()
                .collect(Collectors.toMap(
                        row -> (Long) row[0],
                        row -> (Long) row[1]
                ));
    }

    @Transactional(readOnly = true)
    public Set<Long> getLikedPostIds(Long userId, Collection<Long> postIds) {
        if (userId == null || postIds == null || postIds.isEmpty()) {
            return Collections.emptySet();
        }
        return communityPostLikeRepository.findLikedPostIdsByUserIdAndPostIds(userId, postIds);
    }

    @Transactional(readOnly = true)
    public Set<Long> getLikedCommentIds(Long userId, Collection<Long> commentIds) {
        if (userId == null || commentIds == null || commentIds.isEmpty()) {
            return Collections.emptySet();
        }
        return communityCommentLikeRepository.findLikedCommentIdsByUserIdAndCommentIds(userId, commentIds);
    }

    @Transactional(readOnly = true)
    public long getPostLikeCount(Long postId) {
        return communityPostLikeRepository.countByCommunityPostId(postId);
    }

    @Transactional(readOnly = true)
    public long getCommentLikeCount(Long commentId) {
        return communityCommentLikeRepository.countByCommunityCommentId(commentId);
    }

    @Transactional(readOnly = true)
    public boolean isPostLikedByUser(Long userId, Long postId) {
        return userId != null
                && communityPostLikeRepository.findByCommunityPostIdAndUserId(postId, userId).isPresent();
    }

    @Transactional(readOnly = true)
    public boolean isCommentLikedByUser(Long userId, Long commentId) {
        return userId != null
                && communityCommentLikeRepository.findByCommunityCommentIdAndUserId(commentId, userId).isPresent();
    }

    private void validatePostExists(Long postId) {
        if (!communityPostRepository.existsById(postId)) {
            throw new CustomException(ErrorCode.COMMUNITY_POST_NOT_FOUND);
        }
    }

    private void validateCommentExists(Long commentId) {
        if (!communityCommentRepository.existsById(commentId)) {
            throw new CustomException(ErrorCode.COMMUNITY_COMMENT_NOT_FOUND);
        }
    }
}
