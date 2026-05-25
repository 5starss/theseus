package com.s14p21a503.coreapi.domain.stock.service;

import com.s14p21a503.coreapi.common.infra.redis.RedisService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class StockCurrentPriceService {

    private final RedisService redisService;

    public Map<String, BigDecimal> getCurrentPrices(Collection<String> tickers) {
        if (tickers == null || tickers.isEmpty()) {
            return Map.of();
        }

        List<String> tickerList = tickers.stream()
                .distinct()
                .toList();

        List<String> currentKeys = tickerList.stream()
                .map(ticker -> "stocks:current:" + ticker)
                .toList();
        Map<String, String> currentResults = redisService.getHashFieldBulk(currentKeys, "price");

        List<String> fallbackTickers = tickerList.stream()
                .filter(ticker -> !currentResults.containsKey("stocks:current:" + ticker))
                .toList();

        Map<String, String> infoResults = Map.of();
        if (!fallbackTickers.isEmpty()) {
            List<String> infoKeys = fallbackTickers.stream()
                    .map(ticker -> "stocks:info:" + ticker)
                    .toList();
            infoResults = redisService.getHashFieldBulk(infoKeys, "currentPrice");
        }

        Map<String, BigDecimal> priceMap = new HashMap<>();
        for (String ticker : tickerList) {
            String price = currentResults.getOrDefault(
                    "stocks:current:" + ticker,
                    infoResults.get("stocks:info:" + ticker)
            );

            if (price == null) {
                log.warn("Redis 시세 누락 - ticker: {} (stocks:current, stocks:info 모두 없음)", ticker);
                continue;
            }

            try {
                priceMap.put(ticker, new BigDecimal(price));
            } catch (NumberFormatException e) {
                log.warn("Redis 가격 파싱 실패 - ticker: {}, value: '{}'", ticker, price);
            }
        }

        return priceMap;
    }
}
