package com.s14p21a503.coreapi.domain.community.repository;

import com.s14p21a503.coreapi.domain.community.entity.CommunityPost;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface CommunityPostRepository extends JpaRepository<CommunityPost, Long> {

    Page<CommunityPost> findByTickerOrderByCreatedAtDescIdDesc(String ticker, Pageable pageable);

    Page<CommunityPost> findByTickerOrderByCommentCountDescCreatedAtDescIdDesc(String ticker, Pageable pageable);

    Page<CommunityPost> findByTickerOrderByViewCountDescCreatedAtDescIdDesc(String ticker, Pageable pageable);

    @Query(
            value = """
                    SELECT p.*
                    FROM community_posts p
                    LEFT JOIN community_post_likes l ON l.community_post_id = p.community_post_id
                    WHERE p.ticker = :ticker
                    GROUP BY p.community_post_id
                    ORDER BY COUNT(l.community_post_like_id) DESC, p.created_at DESC, p.community_post_id DESC
                    """,
            countQuery = """
                    SELECT COUNT(*)
                    FROM community_posts p
                    WHERE p.ticker = :ticker
                    """,
            nativeQuery = true
    )
    Page<CommunityPost> findByTickerOrderByLikeCountDesc(@Param("ticker") String ticker, Pageable pageable);
}
