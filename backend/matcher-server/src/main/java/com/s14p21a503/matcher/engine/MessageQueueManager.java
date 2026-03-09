package com.s14p21a503.matcher.engine;

import com.s14p21a503.matcher.dto.OrderRequest;
import com.s14p21a503.matcher.journal.JournaledEvent;
import org.springframework.stereotype.Component;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;

@Component
public class MessageQueueManager {

    private final ConcurrentHashMap<String, BlockingQueue<Object>> queues = new ConcurrentHashMap<>();

    // OOM 방지를 위한 Bounded Queue (용량 100,000 설정)
    private static final int QUEUE_CAPACITY = 100_000;

    public BlockingQueue<Object> getQueue(String ticker) {
        return queues.computeIfAbsent(ticker, k -> new LinkedBlockingQueue<>(QUEUE_CAPACITY));
    }

    public void enqueue(String ticker, long seqNo, Object event) {
        try {
            getQueue(ticker).put(new JournaledEvent(seqNo, event));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("주문 큐 적재 실패", e);
        }
    }

    public JournaledEvent takeOrder(String ticker) throws InterruptedException {
        return (JournaledEvent) getQueue(ticker).take();
    }

    public int getQueueSize(String ticker) {
        BlockingQueue<Object> queue = queues.get(ticker);
        return queue != null ? queue.size() : 0;
    }
}
