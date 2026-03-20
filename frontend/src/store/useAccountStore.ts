import { create } from 'zustand';
import { accountApi, type AccountType } from '../api/account';
import { orderApi, type PendingOrder, type OrderHistory as ApiOrderHistory } from '../api/order';
import { positionApi } from '../api/position';
import { stockApi } from '../api/stock';

export interface PortfolioItem {
    code: string;
    name: string;
    shares: number;
    availableShares: number;
    avgPrice: number;
    currentPrice: number;
}

export interface Transaction {
    id: string;
    date: string;
    time: string;
    type: 'deposit' | 'withdrawal' | 'buy' | 'sell';
    amount: number;
    description: string;
    stockName?: string;
    quantity?: number;
    remainingBalance: number;
}

export interface Order {
    id: string;
    date: string;
    stockCode: string;
    stockName: string;
    type: 'buy' | 'sell';
    status: 'completed' | 'canceled' | 'pending' | 'canceling';
    quantity: number;
    price: number;
}

interface AccountState {
    // Account Selection
    currentAccountType: AccountType;
    setAccountType: (type: AccountType) => void;

    // Total Balances
    totalAssets: number;
    totalInvested: number;
    totalEvaluated: number;
    cashBalance: number;
    totalCash: number;

    // Portfolio
    portfolio: PortfolioItem[];

    // History
    transactions: Transaction[];
    transactionsPage: number;
    transactionsTotalPages: number;
    pendingOrders: Order[];
    completedOrders: Order[];
    pendingOrdersPage: number;
    pendingOrdersTotalPages: number;
    ordersPage: number;
    ordersTotalPages: number;

    // Actions
    fetchBalance: () => Promise<void>;
    fetchPositions: () => Promise<void>;
    fetchTransactions: (params?: { year?: number; month?: number; page?: number; size?: number }) => Promise<void>;
    fetchPendingOrders: (params?: { page?: number; size?: number }) => Promise<void>;
    fetchCompletedOrders: (params?: { page?: number; size?: number; ticker?: string; yearMonth?: string }) => Promise<void>;
    cancelOrder: (orderId: number | string) => Promise<void>;
    executeTrade: (trade: { stockName: string; stockCode: string; quantity: number; price: number; type: 'buy' | 'sell' }) => void;
}

export const useAccountStore = create<AccountState>((set, get) => ({
    // Account Selection
    currentAccountType: 'USER',
    setAccountType: (type) => {
        set({ currentAccountType: type });
        // 계좌 타입이 바뀌면 모든 데이터 초기화 및 다시 가져오기
        get().fetchBalance();
        get().fetchPositions();
        get().fetchPendingOrders();
        get().fetchCompletedOrders();
        get().fetchTransactions({ size: 500 }); // 평단가 추적을 위해 500건 갱신
    },

    totalAssets: 0,
    totalInvested: 0,
    totalEvaluated: 0,
    cashBalance: 0,
    totalCash: 0,
    portfolio: [],
    transactions: [],
    transactionsPage: 0,
    transactionsTotalPages: 0,
    pendingOrders: [],
    completedOrders: [],
    pendingOrdersPage: 0,
    pendingOrdersTotalPages: 0,
    ordersPage: 0,
    ordersTotalPages: 0,

    // 총 예수금, 주문 가능 금액을 가져오는 함수
    fetchBalance: async () => {
        try {
            const { currentAccountType } = get();
            const balance = await accountApi.getBalance(currentAccountType);
            const totalCash = Number(balance.dncaTotAmt);
            const totalEvaluated = get().totalEvaluated || 0;

            set({
                totalCash: totalCash,
                cashBalance: Number(balance.availableAmt),
                totalAssets: totalCash + totalEvaluated,
            });
        } catch (error) {
            console.error('Failed to fetch balance in store:', error);
        }
    },

    // 보유 종목 정보를 가져오는 함수
    fetchPositions: async () => {
        try {
            const { currentAccountType } = get();
            const positions = await positionApi.getPositions(currentAccountType);

            // 각 종목별 현재가 병렬 조회
            const portfolioWithPrices: PortfolioItem[] = await Promise.all(
                positions.map(async (p) => {
                    let currentPrice = p.averagePrice;
                    try {
                        const tick = await stockApi.getTickSnapshot(p.ticker);
                        if (tick) currentPrice = tick.currentPrice;
                    } catch (e) {
                        console.warn(`Failed to fetch price for ${p.ticker}`, e);
                    }

                    return {
                        code: p.ticker,
                        name: p.companyName,
                        shares: p.quantity,
                        availableShares: p.availableQuantity,
                        avgPrice: p.averagePrice,
                        currentPrice: currentPrice
                    };
                })
            );

            const totalInvested = portfolioWithPrices.reduce((acc, item) => acc + (item.shares * item.avgPrice), 0);
            const totalEvaluated = portfolioWithPrices.reduce((acc, item) => acc + (item.shares * item.currentPrice), 0);
            const totalCash = get().totalCash;

            set({
                portfolio: portfolioWithPrices,
                totalInvested,
                totalEvaluated,
                totalAssets: totalCash + totalEvaluated
            });
        } catch (error) {
            console.error('Failed to fetch positions in store:', error);
        }
    },

    // 실제 계좌 거래 내역(입출금, 체결)을 가져오는 함수
    fetchTransactions: async (params) => {
        try {
            const { currentAccountType } = get();
            const data = await accountApi.getHistory({ 
                ...params, 
                account_type: currentAccountType 
            });

            const transformed: Transaction[] = data.histories.content.map(item => {
                const date = new Date(item.executedAt);
                const monthDay = `${date.getMonth() + 1}.${date.getDate()}`;
                const time = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;

                let description = item.stockName || '입출금';
                if (item.transactionType === 'DEPOSIT') description = '입금';
                else if (item.transactionType === 'WITHDRAWAL') description = '출금';

                let amount = Number(item.amount);
                if (item.transactionType === 'BUY' || item.transactionType === 'WITHDRAWAL') {
                    amount = -Math.abs(amount);
                } else {
                    amount = Math.abs(amount);
                }

                return {
                    id: item.historyId.toString(),
                    date: monthDay,
                    time: time,
                    type: item.transactionType.toLowerCase() as 'deposit' | 'withdrawal' | 'buy' | 'sell',
                    amount: amount,
                    description: description,
                    stockName: item.stockName,
                    quantity: item.quantity,
                    remainingBalance: Number(item.balanceAfter)
                };
            });

            set({ 
                transactions: transformed,
                transactionsPage: data.histories.page,
                transactionsTotalPages: data.histories.totalPages
            });
        } catch (error) {
            console.error('Failed to fetch transactions in store:', error);
        }
    },

    // 미체결 주문 내역을 가져오는 함수
    fetchPendingOrders: async (params) => {
        try {
            const { currentAccountType } = get();
            const data = await orderApi.getOrders({ 
                ...params, 
                status: 'PENDING',
                account_type: currentAccountType
            });

            const transformDate = (isoDate: string) => {
                const date = new Date(isoDate);
                return `${date.getMonth() + 1}.${date.getDate()}`;
            };

            const transformedPending: Order[] = data.pending.content.map((po: PendingOrder) => ({
                id: po.orderId.toString(),
                date: transformDate(po.createdAt),
                stockCode: po.ticker,
                stockName: po.companyName,
                type: po.orderType.toLowerCase() as 'buy' | 'sell',
                status: po.status === 'PENDING_CANCEL' ? 'canceling' : 'pending',
                quantity: po.unexecutedQuantity,
                price: po.totalPrice / po.unexecutedQuantity
            }));

            set({ 
                pendingOrders: transformedPending,
                pendingOrdersPage: data.pending.page,
                pendingOrdersTotalPages: data.pending.totalPages
            });
        } catch (error) {
            console.error('Failed to fetch pending orders in store:', error);
        }
    },

    // 체결 및 취소된 주문 내역을 가져오는 함수 (페이징 적용)
    fetchCompletedOrders: async (params) => {
        try {
            const { currentAccountType } = get();
            const data = await orderApi.getOrders({ 
                ...params, 
                status: 'COMPLETED',
                account_type: currentAccountType
            });

            const transformDate = (isoDate: string) => {
                const date = new Date(isoDate);
                return `${date.getMonth() + 1}.${date.getDate()}`;
            };

            const transformedCompleted: Order[] = data.completed.content.map((oh: ApiOrderHistory) => ({
                id: oh.historyId.toString(),
                date: transformDate(oh.createdAt),
                stockCode: oh.ticker,
                stockName: oh.companyName,
                type: oh.orderType.toLowerCase() as 'buy' | 'sell',
                status: oh.historyType === 'EXECUTION' ? 'completed' : 'canceled',
                quantity: oh.quantity,
                price: oh.price
            }));

            set({ 
                completedOrders: transformedCompleted,
                ordersPage: data.completed.page,
                ordersTotalPages: data.completed.totalPages
            });
        } catch (error) {
            console.error('Failed to fetch completed orders in store:', error);
        }
    },

    // 주문을 취소하는 함수
    cancelOrder: async (orderId) => {
        try {
            set((state) => {
                const newPending = state.pendingOrders.map(o =>
                    o.id === String(orderId)
                        ? { ...o, status: 'canceling' as const }
                        : o
                );
                return { pendingOrders: newPending };
            });

            await orderApi.cancelOrder(orderId);

            setTimeout(async () => {
                const { fetchBalance, fetchPendingOrders, fetchCompletedOrders } = get();
                await Promise.all([fetchBalance(), fetchPendingOrders(), fetchCompletedOrders()]);
            }, 1000);

        } catch (error) {
            console.error('Failed to cancel order in store:', error);
            await get().fetchPendingOrders();
            await get().fetchCompletedOrders();
            throw error;
        }
    },

    // 주문을 실행하는 함수
    executeTrade: async (trade) => {
        const { stockCode, quantity, price, type } = trade;
        const { currentAccountType } = get();

        try {
            await orderApi.createOrder({
                ticker: stockCode,
                order_type: type.toUpperCase() as 'BUY' | 'SELL',
                price_type: 'LIMIT',
                price: price,
                quantity: quantity,
                account_type: currentAccountType
            });

            const { fetchBalance, fetchPositions, fetchPendingOrders, fetchCompletedOrders } = get();
            await Promise.all([
                fetchBalance(),
                fetchPositions(),
                fetchPendingOrders(),
                fetchCompletedOrders()
            ]);

            setTimeout(() => {
                const state = get();
                state.fetchBalance();
                state.fetchPositions();
                state.fetchPendingOrders();
                state.fetchCompletedOrders();
            }, 1000);

            setTimeout(() => {
                const state = get();
                state.fetchBalance();
                state.fetchPositions();
                state.fetchPendingOrders();
                state.fetchCompletedOrders();
            }, 2500);

        } catch (error) {
            console.error('Failed to execute trade:', error);
            throw error;
        }
    }
}));

