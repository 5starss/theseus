package com.s14p21a503.matcher.engine;

import com.s14p21a503.matcher.util.ExecutionIdGenerator;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

@Component
@RequiredArgsConstructor
public class PendingOrderManagerHolder {

    private final ExecutionIdGenerator executionIdGenerator;

    @Value("${matcher.participation-rate:1.0}")
    private double participationRate;

    @Value("${matcher.small-cap-participation-rate:1.0}")
    private double smallCapParticipationRate;

    private final ConcurrentHashMap<String, PendingOrderManager> managers = new ConcurrentHashMap<>();

    public PendingOrderManager getManager(String ticker) {
        return managers.computeIfAbsent(ticker,
                key -> new PendingOrderManager(key, executionIdGenerator, 
                        BigDecimal.valueOf(participationRate), BigDecimal.valueOf(smallCapParticipationRate)));
    }

    public Set<String> getTickers() {
        return managers.keySet();
    }

    public void clear() {
        managers.clear();
    }
}
