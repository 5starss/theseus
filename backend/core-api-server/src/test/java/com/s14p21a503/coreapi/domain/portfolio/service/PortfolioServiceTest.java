package com.s14p21a503.coreapi.domain.portfolio.service;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.account.repository.AccountRepository;
import com.s14p21a503.coreapi.domain.portfolio.dto.PortfolioSummaryResponseDto;
import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.position.repository.PositionRepository;
import com.s14p21a503.coreapi.domain.stock.entity.Stock;
import com.s14p21a503.coreapi.domain.stock.service.StockCurrentPriceService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PortfolioServiceTest {

    @Mock
    private AccountRepository accountRepository;

    @Mock
    private PositionRepository positionRepository;

    @Mock
    private StockCurrentPriceService stockCurrentPriceService;

    @InjectMocks
    private PortfolioService portfolioService;

    @Test
    void getMyPortfolioSummaryCalculatesTotalsAndWeights() {
        Long userId = 1L;
        Account account = Account.builder()
                .userId(userId)
                .accountType(AccountType.USER)
                .dncaTotAmt(BigDecimal.ZERO)
                .build();
        setId(account, 10L);

        Position samsung = Position.builder()
                .accountId(10L)
                .userId(userId)
                .ticker("005930")
                .quantity(10)
                .averagePrice(new BigDecimal("70000"))
                .totalPurchaseAmount(new BigDecimal("700000"))
                .build();
        setStock(samsung, "삼성전자");

        Position sk = Position.builder()
                .accountId(10L)
                .userId(userId)
                .ticker("000660")
                .quantity(5)
                .averagePrice(new BigDecimal("120000"))
                .totalPurchaseAmount(new BigDecimal("600000"))
                .build();
        setStock(sk, "SK하이닉스");

        Position empty = Position.builder()
                .accountId(10L)
                .userId(userId)
                .ticker("035420")
                .quantity(0)
                .averagePrice(new BigDecimal("200000"))
                .totalPurchaseAmount(BigDecimal.ZERO)
                .build();

        when(accountRepository.findByUserIdAndAccountType(userId, AccountType.USER)).thenReturn(Optional.of(account));
        when(positionRepository.findAllWithStockByAccountId(10L)).thenReturn(List.of(samsung, sk, empty));
        when(stockCurrentPriceService.getCurrentPrices(List.of("005930", "000660"))).thenReturn(Map.of(
                "005930", new BigDecimal("75000"),
                "000660", new BigDecimal("100000")
        ));

        PortfolioSummaryResponseDto response = portfolioService.getMyPortfolioSummary(userId);

        assertThat(response.getHoldingCount()).isEqualTo(2);
        assertThat(response.getTotalEvaluationAmount()).isEqualByComparingTo("1250000");
        assertThat(response.getTotalPurchaseAmount()).isEqualByComparingTo("1300000");
        assertThat(response.getTotalProfitLoss()).isEqualByComparingTo("-50000");
        assertThat(response.getTotalProfitRate()).isEqualByComparingTo("-3.85");
        assertThat(response.getItems()).hasSize(2);

        PortfolioSummaryResponseDto.PortfolioItemDto samsungItem = response.getItems().stream()
                .filter(item -> item.getStockCode().equals("005930"))
                .findFirst()
                .orElseThrow();
        assertThat(samsungItem.getEvaluationAmount()).isEqualByComparingTo("750000");
        assertThat(samsungItem.getProfitLoss()).isEqualByComparingTo("50000");
        assertThat(samsungItem.getProfitRate()).isEqualByComparingTo("7.14");
        assertThat(samsungItem.getPortfolioWeight()).isEqualByComparingTo("60.00");
    }

    @Test
    void getMyPortfolioSummaryThrowsWhenAccountMissing() {
        when(accountRepository.findByUserIdAndAccountType(1L, AccountType.USER)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> portfolioService.getMyPortfolioSummary(1L))
                .isInstanceOf(CustomException.class);
    }

    @Test
    void getMyPortfolioSummaryReturnsEmptyWhenNoHoldings() {
        Long userId = 1L;
        Account account = Account.builder()
                .userId(userId)
                .accountType(AccountType.USER)
                .dncaTotAmt(BigDecimal.ZERO)
                .build();
        setId(account, 10L);

        when(accountRepository.findByUserIdAndAccountType(userId, AccountType.USER)).thenReturn(Optional.of(account));
        when(positionRepository.findAllWithStockByAccountId(10L)).thenReturn(List.of());

        PortfolioSummaryResponseDto response = portfolioService.getMyPortfolioSummary(userId);

        assertThat(response.getHoldingCount()).isZero();
        assertThat(response.getItems()).isEmpty();
        assertThat(response.getTotalEvaluationAmount()).isEqualByComparingTo("0");
        assertThat(response.getTotalProfitRate()).isEqualByComparingTo("0.00");
    }

    private void setId(Account account, Long id) {
        try {
            var field = Account.class.getDeclaredField("id");
            field.setAccessible(true);
            field.set(account, id);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(e);
        }
    }

    private void setStock(Position position, String companyName) {
        try {
            Stock stock = Stock.builder()
                    .ticker(position.getTicker())
                    .companyName(companyName)
                    .build();

            var field = Position.class.getDeclaredField("stock");
            field.setAccessible(true);
            field.set(position, stock);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(e);
        }
    }
}
