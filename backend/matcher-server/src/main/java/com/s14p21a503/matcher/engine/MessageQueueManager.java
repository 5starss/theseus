package com.s14p21a503.matcher.engine;

import com.s14p21a503.matcher.dto.OrderRequest;
import com.s14p21a503.matcher.dto.OrderType;
import org.springframework.stereotype.Component;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;

@Component
public class MessageQueueManager {

    private final ConcurrentHashMap<String, BlockingQueue<OrderRequest>> queues = new ConcurrentHashMap<>();

    // OOM 방지를 위한 Bounded Queue (용량 100,000 설정)
    private static final int QUEUE_CAPACITY = 100_000;
    
    public BlockingQueue<OrderRequest> getQueue(String ticker) {
        return queues.computeIfAbsent(ticker, k -> new LinkedBlockingQueue<>(QUEUE_CAPACITY));
    }

    public void enqueue(OrderRequest order) {
        try {
            getQueue(order.getTicker()).put(order);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("주문 큐 적재 실패", e);
        }
    }

    public OrderRequest takeOrder(String ticker) throws InterruptedException {
        return getQueue(ticker).take();
    }
    
    public int getQueueSize(String ticker) {
        BlockingQueue<OrderRequest> queue = queues.get(ticker);
        return queue != null ? queue.size() : 0;
    }
}
