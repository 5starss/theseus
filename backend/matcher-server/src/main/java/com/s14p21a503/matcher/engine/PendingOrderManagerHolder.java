package com.s14p21a503.matcher.engine;

import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;

@Component
public class PendingOrderManagerHolder {

    private final ConcurrentHashMap<String, PendingOrderManager> managers = new ConcurrentHashMap<>();

    public PendingOrderManager getManager(String ticker) {
        return managers.computeIfAbsent(ticker, key -> new PendingOrderManager(key));
    }
}
