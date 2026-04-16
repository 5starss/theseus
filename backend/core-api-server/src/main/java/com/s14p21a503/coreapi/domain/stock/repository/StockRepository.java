package com.s14p21a503.coreapi.domain.stock.repository;

import com.s14p21a503.coreapi.domain.stock.entity.Stock;
import org.springframework.data.jpa.repository.JpaRepository;

public interface StockRepository extends JpaRepository<Stock, String> {
}
