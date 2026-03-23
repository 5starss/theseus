package com.s14p21a503.coreapi.domain.watchlist.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import com.s14p21a503.coreapi.domain.stock.repository.StockRepository;
import com.s14p21a503.coreapi.domain.user.repository.UserRepository;
import com.s14p21a503.coreapi.domain.watchlist.dto.WatchlistCreateRequestDto;
import com.s14p21a503.coreapi.domain.watchlist.dto.WatchlistResponseDto;
import com.s14p21a503.coreapi.domain.watchlist.entity.Watchlist;
import com.s14p21a503.coreapi.domain.watchlist.repository.WatchlistRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class WatchlistService {

    private final WatchlistRepository watchlistRepository;
    private final StockRepository stockRepository;
    private final UserRepository userRepository;
    private final AccountRepository accountRepository;
    private final PositionRepository positionRepository;

    @Transactional
    public void createWatchlist(Long userId, WatchlistCreateRequestDto requestDto) {
        validateUser(userId);
        String ticker = normalizeTicker(requestDto.getTicker());

        if (!stockRepository.existsById(ticker)) {
            throw new CustomException(ErrorCode.STOCK_NOT_FOUND);
        }

        if (watchlistRepository.existsByUserIdAndTicker(userId, ticker)) {
            throw new CustomException(ErrorCode.WATCHLIST_ALREADY_EXISTS);
        }

        watchlistRepository.save(
                Watchlist.builder()
                        .userId(userId)
                        .ticker(ticker)
                        .build()
        );
    }

    @Transactional
    public void deleteWatchlist(Long userId, String ticker) {
        validateUser(userId);
        String normalizedTicker = normalizeTicker(ticker);

        Watchlist watchlist = watchlistRepository.findByUserIdAndTicker(userId, normalizedTicker)
                .orElseThrow(() -> new CustomException(ErrorCode.WATCHLIST_NOT_FOUND));

        watchlistRepository.delete(watchlist);
    }

    @Transactional(readOnly = true)
    public List<WatchlistResponseDto> getWatchlists(Long userId) {
        validateUser(userId);

        List<Watchlist> watchlists = watchlistRepository.findAllWithStockByUserId(userId);
        Map<String, Position> positionByTicker = getPositionByTicker(userId);

        return watchlists.stream()
                .map(watchlist -> WatchlistResponseDto.from(watchlist, positionByTicker.get(watchlist.getTicker())))
                .toList();
    }

    private Map<String, Position> getPositionByTicker(Long userId) {
        return accountRepository.findByUserIdAndAccountType(userId, AccountType.USER)
                .map(Account::getId)
                .map(positionRepository::findAllWithStockByAccountId)
                .orElse(Collections.emptyList())
                .stream()
                .collect(Collectors.toMap(Position::getTicker, Function.identity(), (left, right) -> left));
    }

    private void validateUser(Long userId) {
        if (!userRepository.existsById(userId)) {
            throw new CustomException(ErrorCode.USER_NOT_FOUND);
        }
    }

    private String normalizeTicker(String ticker) {
        if (ticker == null || ticker.isBlank()) {
            throw new CustomException(ErrorCode.INVALID_INPUT_VALUE);
        }
        return ticker.trim();
    }
}
