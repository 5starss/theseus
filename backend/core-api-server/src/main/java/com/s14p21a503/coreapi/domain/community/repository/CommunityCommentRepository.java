package com.s14p21a503.coreapi.domain.community.repository;

import com.s14p21a503.coreapi.domain.community.entity.CommunityComment;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface CommunityCommentRepository extends JpaRepository<CommunityComment, Long> {

    List<CommunityComment> findByPostIdOrderByCreatedAtAscIdAsc(Long postId);

    void deleteByPostId(Long postId);
}
