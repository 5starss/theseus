package com.s14p21a503.coreapi.domain.stock.entity;

import com.s14p21a503.coreapi.common.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "stocks")
public class Stock extends BaseEntity {

    @Id
    @Column(name = "ticker", length = 20, nullable = false)
    private String ticker;

    @Column(name = "company_name", length = 100, nullable = false)
    private String companyName;

    @Column(name = "market_type", length = 20, nullable = false)
    private String marketType;

    @Column(name = "status", length = 20, nullable = false)
    private String status;

    @Column(name = "logo_url")
    private String logoUrl;

    @Builder
    public Stock(String ticker, String companyName, String marketType, String status, String logoUrl) {
        this.ticker = ticker;
        this.companyName = companyName;
        this.marketType = marketType != null ? marketType : "UNKNOWN";
        this.status = status != null ? status : "ACTIVE";
        this.logoUrl = logoUrl;
    }
}
