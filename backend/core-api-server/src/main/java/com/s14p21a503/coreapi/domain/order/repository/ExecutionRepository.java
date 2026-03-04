package com.s14p21a503.coreapi.domain.order.repository;

import com.s14p21a503.coreapi.domain.order.entity.Execution;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ExecutionRepository extends JpaRepository<Execution, Long> {
}
