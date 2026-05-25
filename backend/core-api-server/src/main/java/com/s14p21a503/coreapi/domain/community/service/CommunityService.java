package com.s14p21a503.coreapi.domain.community.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.PageResponseDto;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.community.dto.CommunityCommentCreateRequestDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityCommentResponseDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityCommentUpdateRequestDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostCreateRequestDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostDetailResponseDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostSummaryResponseDto;
import com.s14p21a503.coreapi.domain.community.dto.CommunityPostUpdateRequestDto;
import com.s14p21a503.coreapi.domain.community.entity.CommunityComment;
import com.s14p21a503.coreapi.domain.community.entity.CommunityPost;
import com.s14p21a503.coreapi.domain.community.repository.CommunityCommentRepository;
import com.s14p21a503.coreapi.domain.community.repository.CommunityPostRepository;
import com.s14p21a503.coreapi.domain.stock.entity.Stock;
import com.s14p21a503.coreapi.domain.stock.repository.StockRepository;
import com.s14p21a503.coreapi.domain.user.entity.User;
import com.s14p21a503.coreapi.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CommunityService {

    private final CommunityPostRepository communityPostRepository;
    private final CommunityCommentRepository communityCommentRepository;
    private final StockRepository stockRepository;
    private final UserRepository userRepository;
    private final ShareholderBadgeService shareholderBadgeService;
    private final CommunityLikeService communityLikeService;

    @Transactional(readOnly = true)
    public PageResponseDto<CommunityPostSummaryResponseDto> getPosts(
            Long userId,
            String stockId,
            String stockCode,
            Pageable pageable
    ) {
        String ticker = resolveTicker(stockId, stockCode);
        Stock stock = getStock(ticker);

        Page<CommunityPost> postPage = communityPostRepository.findByTickerOrderByCreatedAtDescIdDesc(ticker, pageable);
        Set<Long> userIds = extractPostUserIds(postPage.getContent());
        Set<Long> postIds = extractPostIds(postPage.getContent());
        Map<Long, String> nicknameMap = getNicknameMap(userIds);
        Map<Long, Boolean> shareholderMap = shareholderBadgeService.getShareholderMap(ticker, userIds);
        Map<Long, Long> likeCountMap = communityLikeService.getPostLikeCountMap(postIds);
        Set<Long> likedPostIds = communityLikeService.getLikedPostIds(userId, postIds);

        Page<CommunityPostSummaryResponseDto> mappedPage = postPage.map(post -> CommunityPostSummaryResponseDto.builder()
                .postId(post.getId())
                .stockCode(post.getTicker())
                .stockName(stock.getCompanyName())
                .title(post.getTitle())
                .authorId(post.getUserId())
                .authorNickname(nicknameMap.getOrDefault(post.getUserId(), "Unknown user"))
                .createdAt(post.getCreatedAt())
                .updatedAt(post.getUpdatedAt())
                .viewCount(post.getViewCount())
                .commentCount(post.getCommentCount())
                .likeCount(likeCountMap.getOrDefault(post.getId(), 0L))
                .likedByMe(likedPostIds.contains(post.getId()))
                .isShareholder(shareholderMap.getOrDefault(post.getUserId(), false))
                .build());

        return PageResponseDto.from(mappedPage);
    }

    @Transactional(readOnly = true)
    public CommunityPostDetailResponseDto getPostDetail(Long userId, Long postId) {
        CommunityPost post = getPost(postId);
        Stock stock = getStock(post.getTicker());
        User user = getUser(post.getUserId());

        return CommunityPostDetailResponseDto.builder()
                .postId(post.getId())
                .stockCode(post.getTicker())
                .stockName(stock.getCompanyName())
                .title(post.getTitle())
                .content(post.getContent())
                .authorId(post.getUserId())
                .authorNickname(user.getNickname())
                .createdAt(post.getCreatedAt())
                .updatedAt(post.getUpdatedAt())
                .viewCount(post.getViewCount())
                .commentCount(post.getCommentCount())
                .likeCount(communityLikeService.getPostLikeCount(postId))
                .likedByMe(communityLikeService.isPostLikedByUser(userId, postId))
                .isShareholder(shareholderBadgeService.isShareholder(post.getTicker(), post.getUserId()))
                .build();
    }

    @Transactional
    public CommunityPostDetailResponseDto createPost(Long userId, CommunityPostCreateRequestDto requestDto) {
        User user = getUser(userId);
        String ticker = resolveTicker(requestDto.getStockId(), requestDto.getStockCode());
        Stock stock = getStock(ticker);

        CommunityPost post = communityPostRepository.save(
                CommunityPost.builder()
                        .userId(user.getId())
                        .ticker(ticker)
                        .title(normalizeRequiredText(requestDto.getTitle()))
                        .content(normalizeRequiredText(requestDto.getContent()))
                        .build()
        );

        return toPostDetailResponse(post, userId, user.getNickname(), stock.getCompanyName());
    }

    @Transactional
    public CommunityPostDetailResponseDto updatePost(Long userId, Long postId, CommunityPostUpdateRequestDto requestDto) {
        CommunityPost post = getPost(postId);
        validateAuthor(userId, post.getUserId());

        post.update(
                normalizeRequiredText(requestDto.getTitle()),
                normalizeRequiredText(requestDto.getContent())
        );

        User user = getUser(post.getUserId());
        Stock stock = getStock(post.getTicker());
        return toPostDetailResponse(post, userId, user.getNickname(), stock.getCompanyName());
    }

    @Transactional
    public void deletePost(Long userId, Long postId) {
        CommunityPost post = getPost(postId);
        validateAuthor(userId, post.getUserId());

        communityCommentRepository.deleteByPostId(postId);
        communityPostRepository.delete(post);
    }

    @Transactional
    public void increaseViewCount(Long postId) {
        CommunityPost post = getPost(postId);
        post.increaseViewCount();
    }

    @Transactional(readOnly = true)
    public List<CommunityCommentResponseDto> getComments(Long userId, Long postId) {
        CommunityPost post = getPost(postId);
        List<CommunityComment> comments = communityCommentRepository.findByPostIdOrderByCreatedAtAscIdAsc(postId);
        Set<Long> userIds = extractCommentUserIds(comments);
        Set<Long> commentIds = extractCommentIds(comments);
        Map<Long, String> nicknameMap = getNicknameMap(userIds);
        Map<Long, Boolean> shareholderMap = shareholderBadgeService.getShareholderMap(post.getTicker(), userIds);
        Map<Long, Long> likeCountMap = communityLikeService.getCommentLikeCountMap(commentIds);
        Set<Long> likedCommentIds = communityLikeService.getLikedCommentIds(userId, commentIds);

        return comments.stream()
                .map(comment -> CommunityCommentResponseDto.builder()
                        .commentId(comment.getId())
                        .postId(comment.getPostId())
                        .authorId(comment.getUserId())
                        .authorNickname(nicknameMap.getOrDefault(comment.getUserId(), "Unknown user"))
                        .content(comment.getContent())
                        .createdAt(comment.getCreatedAt())
                        .updatedAt(comment.getUpdatedAt())
                        .likeCount(likeCountMap.getOrDefault(comment.getId(), 0L))
                        .likedByMe(likedCommentIds.contains(comment.getId()))
                        .isShareholder(shareholderMap.getOrDefault(comment.getUserId(), false))
                        .build())
                .toList();
    }

    @Transactional
    public CommunityCommentResponseDto createComment(Long userId, Long postId, CommunityCommentCreateRequestDto requestDto) {
        CommunityPost post = getPost(postId);
        User user = getUser(userId);

        CommunityComment comment = communityCommentRepository.save(
                CommunityComment.builder()
                        .postId(postId)
                        .userId(user.getId())
                        .content(normalizeRequiredText(requestDto.getContent()))
                        .build()
        );
        post.increaseCommentCount();

        return toCommentResponse(comment, userId, user.getNickname(), post.getTicker());
    }

    @Transactional
    public CommunityCommentResponseDto updateComment(Long userId, Long commentId, CommunityCommentUpdateRequestDto requestDto) {
        CommunityComment comment = getComment(commentId);
        validateAuthor(userId, comment.getUserId());

        comment.updateContent(normalizeRequiredText(requestDto.getContent()));

        User user = getUser(comment.getUserId());
        CommunityPost post = getPost(comment.getPostId());
        return toCommentResponse(comment, userId, user.getNickname(), post.getTicker());
    }

    @Transactional
    public void deleteComment(Long userId, Long commentId) {
        CommunityComment comment = getComment(commentId);
        validateAuthor(userId, comment.getUserId());

        CommunityPost post = getPost(comment.getPostId());
        post.decreaseCommentCount();
        communityCommentRepository.delete(comment);
    }

    private CommunityPostDetailResponseDto toPostDetailResponse(CommunityPost post, Long viewerUserId, String nickname, String stockName) {
        return CommunityPostDetailResponseDto.builder()
                .postId(post.getId())
                .stockCode(post.getTicker())
                .stockName(stockName)
                .title(post.getTitle())
                .content(post.getContent())
                .authorId(post.getUserId())
                .authorNickname(nickname)
                .createdAt(post.getCreatedAt())
                .updatedAt(post.getUpdatedAt())
                .viewCount(post.getViewCount())
                .commentCount(post.getCommentCount())
                .likeCount(communityLikeService.getPostLikeCount(post.getId()))
                .likedByMe(communityLikeService.isPostLikedByUser(viewerUserId, post.getId()))
                .isShareholder(shareholderBadgeService.isShareholder(post.getTicker(), post.getUserId()))
                .build();
    }

    private CommunityCommentResponseDto toCommentResponse(CommunityComment comment, Long viewerUserId, String nickname, String ticker) {
        return CommunityCommentResponseDto.builder()
                .commentId(comment.getId())
                .postId(comment.getPostId())
                .authorId(comment.getUserId())
                .authorNickname(nickname)
                .content(comment.getContent())
                .createdAt(comment.getCreatedAt())
                .updatedAt(comment.getUpdatedAt())
                .likeCount(communityLikeService.getCommentLikeCount(comment.getId()))
                .likedByMe(communityLikeService.isCommentLikedByUser(viewerUserId, comment.getId()))
                .isShareholder(shareholderBadgeService.isShareholder(ticker, comment.getUserId()))
                .build();
    }

    private CommunityPost getPost(Long postId) {
        return communityPostRepository.findById(postId)
                .orElseThrow(() -> new CustomException(ErrorCode.COMMUNITY_POST_NOT_FOUND));
    }

    private CommunityComment getComment(Long commentId) {
        return communityCommentRepository.findById(commentId)
                .orElseThrow(() -> new CustomException(ErrorCode.COMMUNITY_COMMENT_NOT_FOUND));
    }

    private User getUser(Long userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new CustomException(ErrorCode.USER_NOT_FOUND));
    }

    private Stock getStock(String ticker) {
        return stockRepository.findById(ticker)
                .orElseThrow(() -> new CustomException(ErrorCode.STOCK_NOT_FOUND));
    }

    private void validateAuthor(Long requesterId, Long authorId) {
        if (!authorId.equals(requesterId)) {
            throw new CustomException(ErrorCode.ACCESS_DENIED);
        }
    }

    private String resolveTicker(String stockId, String stockCode) {
        String normalizedStockId = normalizeOptionalText(stockId);
        String normalizedStockCode = normalizeOptionalText(stockCode);

        if (normalizedStockId == null && normalizedStockCode == null) {
            throw new CustomException(ErrorCode.INVALID_INPUT_VALUE);
        }

        if (normalizedStockId != null && normalizedStockCode != null && !normalizedStockId.equals(normalizedStockCode)) {
            throw new CustomException(ErrorCode.INVALID_INPUT_VALUE);
        }

        return normalizedStockCode != null ? normalizedStockCode : normalizedStockId;
    }

    private String normalizeRequiredText(String value) {
        String normalized = normalizeOptionalText(value);
        if (normalized == null) {
            throw new CustomException(ErrorCode.INVALID_INPUT_VALUE);
        }
        return normalized;
    }

    private String normalizeOptionalText(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private Map<Long, String> getNicknameMap(Collection<Long> userIds) {
        if (userIds == null || userIds.isEmpty()) {
            return Collections.emptyMap();
        }

        return userRepository.findAllById(userIds).stream()
                .collect(Collectors.toMap(User::getId, User::getNickname, (left, right) -> left));
    }

    private Set<Long> extractPostUserIds(List<CommunityPost> posts) {
        return posts.stream()
                .map(CommunityPost::getUserId)
                .collect(Collectors.toSet());
    }

    private Set<Long> extractPostIds(List<CommunityPost> posts) {
        return posts.stream()
                .map(CommunityPost::getId)
                .collect(Collectors.toSet());
    }

    private Set<Long> extractCommentUserIds(List<CommunityComment> comments) {
        return comments.stream()
                .map(CommunityComment::getUserId)
                .collect(Collectors.toSet());
    }

    private Set<Long> extractCommentIds(List<CommunityComment> comments) {
        return comments.stream()
                .map(CommunityComment::getId)
                .collect(Collectors.toSet());
    }
}
