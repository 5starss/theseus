package com.s14p21a503.coreapi.domain.community.repository;

import com.s14p21a503.coreapi.domain.community.entity.CommunityPost;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CommunityPostRepository extends JpaRepository<CommunityPost, Long> {

    Page<CommunityPost> findByTickerOrderByCreatedAtDescIdDesc(String ticker, Pageable pageable);
}
