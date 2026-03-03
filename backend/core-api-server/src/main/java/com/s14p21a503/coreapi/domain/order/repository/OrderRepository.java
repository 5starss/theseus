package com.s14p21a503.coreapi.domain.order.repository;

import com.s14p21a503.coreapi.domain.order.entity.Order;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

public interface OrderRepository extends JpaRepository<Order, Long> {
}
