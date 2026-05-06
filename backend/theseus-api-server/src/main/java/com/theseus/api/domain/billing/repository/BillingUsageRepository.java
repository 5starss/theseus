package com.theseus.api.domain.billing.repository;

import com.theseus.api.domain.billing.entity.BillingUsage;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BillingUsageRepository extends JpaRepository<BillingUsage, Long> {

	Optional<BillingUsage> findByIdempotencyKey(String idempotencyKey);
}
