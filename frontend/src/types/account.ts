export type AccountType = 'USER' | 'AI';

export interface Account {
    accountId: string;
    accountType: AccountType;
    balance: number;
    totalAsset: number;
    totalProfit: number;
    totalProfitRate: number;
}

export interface Holding {
    ticker: string;
    stockName: string;
    quantity: number;
    averagePrice: number;
    currentPrice: number;
    profit: number;
    profitRate: number;
    totalValue: number;
}

export interface Transaction {
    id: number;
    ticker: string;
    stockName: string;
    type: 'BUY' | 'SELL';
    price: number;
    quantity: number;
    amount: number;
    fee: number;
    tax: number;
    createdAt: string;
}
