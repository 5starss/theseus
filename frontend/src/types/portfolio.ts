export interface PortfolioHoldingItem {
    stockCode: string;
    stockName: string;
    quantity: number;
    averagePurchasePrice: number;
    currentPrice: number;
    purchaseAmount: number;
    evaluationAmount: number;
    profitLoss: number;
    profitRate: number;
    portfolioWeight: number;
}

export interface PortfolioSummaryResponse {
    totalEvaluationAmount: number;
    totalPurchaseAmount: number;
    totalProfitLoss: number;
    totalProfitRate: number;
    holdingCount: number;
    items: PortfolioHoldingItem[];
}

export type PortfolioFilterType = "all" | "profit" | "loss";
export type PortfolioSortType = "evaluation" | "profitRate" | "weight" | "name";
