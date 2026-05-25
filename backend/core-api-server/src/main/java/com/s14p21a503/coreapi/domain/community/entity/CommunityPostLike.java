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
        name = "community_post_likes",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_community_post_likes_user_post",
                columnNames = {"user_id", "community_post_id"}
        ),
        indexes = {
                @Index(name = "idx_community_post_likes_post_id", columnList = "community_post_id"),
                @Index(name = "idx_community_post_likes_user_id", columnList = "user_id")
        }
)
public class CommunityPostLike {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "community_post_like_id")
    private Long id;

    @Column(name = "community_post_id", nullable = false)
    private Long communityPostId;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Builder
    public CommunityPostLike(Long communityPostId, Long userId) {
        this.communityPostId = communityPostId;
        this.userId = userId;
    }
}
