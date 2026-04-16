package com.s14p21a503.coreapi.domain.watchlist.dto;

import com.s14p21a503.coreapi.domain.position.entity.Position;
import com.s14p21a503.coreapi.domain.stock.entity.Stock;
import com.s14p21a503.coreapi.domain.watchlist.entity.Watchlist;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class WatchlistResponseDto {

    private String ticker;
    private String companyName;
    private String marketType;
    private String logoUrl;
    private Boolean isHeld;
    private Integer quantity;

    public static WatchlistResponseDto from(Watchlist watchlist, Position position) {
        Stock stock = watchlist.getStock();
        int quantity = position != null && position.getQuantity() != null ? position.getQuantity() : 0;

        return WatchlistResponseDto.builder()
                .ticker(watchlist.getTicker())
                .companyName(stock != null ? stock.getCompanyName() : watchlist.getTicker())
                .marketType(stock != null ? stock.getMarketType() : null)
                .logoUrl(stock != null ? stock.getLogoUrl() : null)
                .isHeld(quantity > 0)
                .quantity(quantity)
                .build();
    }
}
