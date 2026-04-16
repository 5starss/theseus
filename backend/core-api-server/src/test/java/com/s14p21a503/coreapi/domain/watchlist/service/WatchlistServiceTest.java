package com.s14p21a503.coreapi.domain.watchlist.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import com.s14p21a503.coreapi.domain.stock.repository.StockRepository;
import com.s14p21a503.coreapi.domain.user.repository.UserRepository;
import com.s14p21a503.coreapi.domain.watchlist.dto.WatchlistCreateRequestDto;
import com.s14p21a503.coreapi.domain.watchlist.repository.WatchlistRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentMatchers;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class WatchlistServiceTest {

    @Mock
    private WatchlistRepository watchlistRepository;

    @Mock
    private StockRepository stockRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private AccountRepository accountRepository;

    @Mock
    private PositionRepository positionRepository;

    @InjectMocks
    private WatchlistService watchlistService;

    @Test
    void createWatchlistThrowsWhenLimitExceeded() {
        Long userId = 1L;
        WatchlistCreateRequestDto requestDto = new WatchlistCreateRequestDto();
        ReflectionTestUtils.setField(requestDto, "ticker", "005930");

        when(userRepository.existsById(userId)).thenReturn(true);
        when(stockRepository.existsById("005930")).thenReturn(true);
        when(watchlistRepository.existsByUserIdAndTicker(userId, "005930")).thenReturn(false);
        when(watchlistRepository.countByUserId(userId)).thenReturn(3L);

        CustomException exception = assertThrows(
                CustomException.class,
                () -> watchlistService.createWatchlist(userId, requestDto)
        );

        assertEquals(ErrorCode.WATCHLIST_LIMIT_EXCEEDED, exception.getErrorCode());
        verify(watchlistRepository, never()).save(ArgumentMatchers.any());
    }
}
