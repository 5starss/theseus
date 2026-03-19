package com.s14p21a503.coreapi.domain.position.service;

import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
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
    private final AccountRepository accountRepository;

    @Transactional(readOnly = true)
    public List<PositionResponseDto> getPositions(Long userId, AccountType accountType) {
        AccountType type = accountType != null ? accountType : AccountType.USER;
        
        Account account = accountRepository.findByUserIdAndAccountType(userId, type)
                .orElseThrow(() -> new CustomException(ErrorCode.ACCOUNT_NOT_FOUND));

        return positionRepository.findAllWithStockByAccountId(account.getId()).stream()
                .map(PositionResponseDto::from)
                .toList();
    }
}
