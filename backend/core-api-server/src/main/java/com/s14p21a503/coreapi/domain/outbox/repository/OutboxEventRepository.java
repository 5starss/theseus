package com.s14p21a503.coreapi.domain.outbox.repository;

import com.s14p21a503.coreapi.domain.outbox.entity.OutboxEvent;
import com.s14p21a503.coreapi.domain.outbox.entity.OutboxStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface OutboxEventRepository extends JpaRepository<OutboxEvent, Long> {

    /**
     * 특정 상태의 이벤트를 오래된 순서대로 조회합니다.
     * 스케줄러(Polling)가 아직 전송되지 않은(INIT) 메시지를 가져올 때 사용합니다.
     */
    // 성능을 위해 Limit 을 거는 것이 좋으나 Spring Data JPA의 기본 메서드 이름으로는 처리가 애매하여 @Query 나 페이징을 사용 가능합니다.
    List<OutboxEvent> findTop50ByStatusOrderByCreatedAtAsc(OutboxStatus status);

    /**
     * 특정 날짜 이전에 전송 완료된 아웃박스 이벤트들을 일괄 삭제합니다.
     * 스토리지 용량 관리 및 인덱스 성능 최적화를 위해 사용됩니다.
     */
    @Modifying
    @Query("DELETE FROM OutboxEvent o WHERE o.status = :status AND o.publishedAt < :cutoffDate")
    int deleteOldEvents(@Param("status") OutboxStatus status, @Param("cutoffDate") LocalDateTime cutoffDate);
}
