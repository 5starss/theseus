package com.s14p21a503.coreapi.domain.community.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "community_comment_likes",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_community_comment_likes_user_comment",
                columnNames = {"user_id", "community_comment_id"}
        ),
        indexes = {
                @Index(name = "idx_community_comment_likes_comment_id", columnList = "community_comment_id"),
                @Index(name = "idx_community_comment_likes_user_id", columnList = "user_id")
        }
)
public class CommunityCommentLike {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "community_comment_like_id")
    private Long id;

    @Column(name = "community_comment_id", nullable = false)
    private Long communityCommentId;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Builder
    public CommunityCommentLike(Long communityCommentId, Long userId) {
        this.communityCommentId = communityCommentId;
        this.userId = userId;
    }
}
