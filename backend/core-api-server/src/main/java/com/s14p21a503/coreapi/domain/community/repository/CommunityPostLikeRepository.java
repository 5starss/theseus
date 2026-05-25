package com.s14p21a503.coreapi.domain.community.repository;

import com.s14p21a503.coreapi.domain.community.entity.CommunityPostLike;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Set;

public interface CommunityPostLikeRepository extends JpaRepository<CommunityPostLike, Long> {

    Optional<CommunityPostLike> findByCommunityPostIdAndUserId(Long communityPostId, Long userId);

    long countByCommunityPostId(Long communityPostId);

    @Query("""
            SELECT l.communityPostId, COUNT(l)
            FROM CommunityPostLike l
            WHERE l.communityPostId IN :postIds
            GROUP BY l.communityPostId
            """)
    List<Object[]> countByCommunityPostIds(@Param("postIds") Collection<Long> postIds);

    @Query("""
            SELECT l.communityPostId
            FROM CommunityPostLike l
            WHERE l.userId = :userId
              AND l.communityPostId IN :postIds
            """)
    Set<Long> findLikedPostIdsByUserIdAndPostIds(
            @Param("userId") Long userId,
            @Param("postIds") Collection<Long> postIds
    );
}
