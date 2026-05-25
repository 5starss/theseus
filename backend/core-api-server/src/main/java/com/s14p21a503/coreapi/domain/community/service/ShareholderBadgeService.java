package com.s14p21a503.coreapi.domain.community.service;

import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ShareholderBadgeService {

    private final PositionRepository positionRepository;

    @Transactional(readOnly = true)
    public boolean isShareholder(String ticker, Long userId) {
        return positionRepository.existsByUserIdAndTickerAndQuantityGreaterThan(userId, ticker, 0);
    }

    @Transactional(readOnly = true)
    public Map<Long, Boolean> getShareholderMap(String ticker, Collection<Long> userIds) {
        if (userIds == null || userIds.isEmpty()) {
            return Collections.emptyMap();
        }

        Set<Long> uniqueUserIds = userIds.stream().collect(Collectors.toSet());
        Set<Long> shareholderIds = positionRepository.findShareholderUserIdsByTickerAndUserIds(ticker, uniqueUserIds);

        return uniqueUserIds.stream()
                .collect(Collectors.toMap(Function.identity(), shareholderIds::contains));
    }
}
