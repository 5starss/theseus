package com.s14p21a503.coreapi.domain.community.repository;

import com.s14p21a503.coreapi.domain.community.entity.CommunityCommentLike;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Set;

public interface CommunityCommentLikeRepository extends JpaRepository<CommunityCommentLike, Long> {

    Optional<CommunityCommentLike> findByCommunityCommentIdAndUserId(Long communityCommentId, Long userId);

    long countByCommunityCommentId(Long communityCommentId);

    @Query("""
            SELECT l.communityCommentId, COUNT(l)
            FROM CommunityCommentLike l
            WHERE l.communityCommentId IN :commentIds
            GROUP BY l.communityCommentId
            """)
    List<Object[]> countByCommunityCommentIds(@Param("commentIds") Collection<Long> commentIds);

    @Query("""
            SELECT l.communityCommentId
            FROM CommunityCommentLike l
            WHERE l.userId = :userId
              AND l.communityCommentId IN :commentIds
            """)
    Set<Long> findLikedCommentIdsByUserIdAndCommentIds(
            @Param("userId") Long userId,
            @Param("commentIds") Collection<Long> commentIds
    );
}
