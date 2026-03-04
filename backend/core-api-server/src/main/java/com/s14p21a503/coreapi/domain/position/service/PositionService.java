package com.s14p21a503.coreapi.domain.position.service;

import com.s14p21a503.coreapi.domain.position.dto.PositionResponseDto;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class PositionService {

    private final PositionRepository positionRepository;

    @Transactional(readOnly = true)
    public List<PositionResponseDto> getPositions(Long userId) {
        return positionRepository.findAllWithStockByUserId(userId).stream()
                .map(PositionResponseDto::from)
                .toList();
    }
}
