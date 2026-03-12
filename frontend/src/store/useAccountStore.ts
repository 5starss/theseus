import { create } from 'zustand';
import { accountApi } from '../api/account';
import { orderApi, type PendingOrder, type OrderHistory as ApiOrderHistory } from '../api/order';
import { positionApi } from '../api/position';
import { stockApi } from '../api/stock';

export interface PortfolioItem {
    code: string;
    name: string;
    shares: number;
    avgPrice: number;
    currentPrice: number; // 현재가 추가
}

export interface Transaction {
    id: string;
    date: string;       // e.g., "2.25", "2.24"
    time: string;       // e.g., "00:27"
    type: 'deposit' | 'withdrawal' | 'buy' | 'sell';
    amount: number;     // e.g. -185100 (negative for buy/withdrawal, positive for sell/deposit)
    description: string;

    // Additional fields for transaction history view
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
    // Total Balances
    totalAssets: number;
    totalInvested: number;      // 총 매수 금액
    totalEvaluated: number;     // 총 평가 금액 (현재가 기준)
    cashBalance: number;        // 주문 가능 금액
    totalCash: number;          // 예수금 총액 (dncaTotAmt)

    // Portfolio
    portfolio: PortfolioItem[];

    // History
    transactions: Transaction[];
    orders: Order[];

    // Actions
    fetchBalance: () => Promise<void>;
    fetchPositions: () => Promise<void>;
    fetchTransactions: (params?: { year?: number; month?: number; page?: number; size?: number }) => Promise<void>;
    fetchOrders: (params?: { page?: number; size?: number; status?: string; ticker?: string; yearMonth?: string }) => Promise<void>;
    cancelOrder: (orderId: number | string) => Promise<void>;
    executeTrade: (trade: { stockName: string; stockCode: string; quantity: number; price: number; type: 'buy' | 'sell' }) => void;
}

export const useAccountStore = create<AccountState>((set) => ({
    totalAssets: 0,
    totalInvested: 0,
    totalEvaluated: 0,
    cashBalance: 0,
    totalCash: 0,
    portfolio: [],
    transactions: [],
    orders: [],

    // 총 예수금, 주문 가능 금액을 가져오는 함수
    fetchBalance: async () => {
        try {
            const balance = await accountApi.getBalance();
            const totalCash = Number(balance.dncaTotAmt);
            const totalEvaluated = useAccountStore.getState().totalEvaluated || 0;

            set({
                totalCash: totalCash,
                cashBalance: Number(balance.availableAmt),
                // totalAssets = 총 예수금 + 주식 평가 금액
                totalAssets: totalCash + totalEvaluated,
            });
        } catch (error) {
            console.error('Failed to fetch balance in store:', error);
        }
    },

    // 보유 종목 정보를 가져오는 함수
    fetchPositions: async () => {
        try {
            const positions = await positionApi.getPositions();

            // 각 종목별 현재가 병렬 조회
            const portfolioWithPrices: PortfolioItem[] = await Promise.all(
                positions.map(async (p) => {
                    let currentPrice = p.averagePrice; // 기본값은 매수가
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
                        avgPrice: p.averagePrice,
                        currentPrice: currentPrice
                    };
                })
            );

            const totalInvested = portfolioWithPrices.reduce((acc, item) => acc + (item.shares * item.avgPrice), 0);
            const totalEvaluated = portfolioWithPrices.reduce((acc, item) => acc + (item.shares * item.currentPrice), 0);
            const totalCash = useAccountStore.getState().totalCash;

            set({
                portfolio: portfolioWithPrices,
                totalInvested,
                totalEvaluated,
                // 총 자산 일관성 유지 (예수금 총액 + 평가 금액)
                totalAssets: totalCash + totalEvaluated
            });
        } catch (error) {
            console.error('Failed to fetch positions in store:', error);
        }
    },

    // 실제 계좌 거래 내역(입출금, 체결)을 가져오는 함수
    fetchTransactions: async (params) => {
        try {
            const data = await accountApi.getHistory(params);

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

            set({ transactions: transformed });
        } catch (error) {
            console.error('Failed to fetch transactions in store:', error);
        }
    },

    // 미체결, 체결 및 취소된 주문 내역을 가져오는 함수
    // params: { page?: number; size?: number; status?: string; ticker?: string; yearMonth?: string }
    fetchOrders: async (params) => {
        try {
            const data = await orderApi.getOrders(params);

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

            set({ orders: [...transformedPending, ...transformedCompleted] });
        } catch (error) {
            console.error('Failed to fetch orders in store:', error);
        }
    },

    // 주문을 취소하는 함수
    cancelOrder: async (orderId) => {
        try {
            // Optimistic update(낙관적 업데이트): 취소 버튼 누르면 바로 취소된 주문으로 변경
            set((state) => {
                const now = new Date();
                const today = `${now.getMonth() + 1}.${now.getDate()}`;
                const newOrders = state.orders.map(o =>
                    o.id === String(orderId)
                        ? { ...o, status: 'canceled' as const, date: today }
                        : o
                );
                return { orders: newOrders };
            });

            // API 호출
            await orderApi.cancelOrder(orderId);

            // 1초 후 백엔드와 동기화
            setTimeout(async () => {
                const getBalance = useAccountStore.getState().fetchBalance;
                const getOrders = useAccountStore.getState().fetchOrders;
                await Promise.all([getBalance(), getOrders()]);
            }, 1000);

        } catch (error) {
            console.error('Failed to cancel order in store:', error);
            // 실패 시 optimistic update 되돌리기
            await useAccountStore.getState().fetchOrders();
        }
    },

    // 주문을 실행하는 함수
    executeTrade: async (trade) => {
        const { stockCode, quantity, price, type } = trade;

        try {
            await orderApi.createOrder({
                ticker: stockCode,
                order_type: type.toUpperCase() as 'BUY' | 'SELL',
                price_type: 'LIMIT', // 현재 지정가 주문만 지원
                price: price,
                quantity: quantity
            });

            // 주문 생성 직후 백엔드와 동기화
            const { fetchBalance, fetchPositions, fetchOrders } = useAccountStore.getState();
            await Promise.all([
                fetchBalance(),
                fetchPositions(),
                fetchOrders()
            ]);

            // 매칭 엔진 처리 시간 고려한 지연 호출 (1초, 2.5초)
            setTimeout(() => {
                const state = useAccountStore.getState();
                state.fetchBalance();
                state.fetchPositions();
                state.fetchOrders();
            }, 1000);

            setTimeout(() => {
                const state = useAccountStore.getState();
                state.fetchBalance();
                state.fetchPositions();
                state.fetchOrders();
            }, 2500);

        } catch (error) {
            console.error('Failed to execute trade:', error);
            throw error; // 컴포넌트에서 에러 표시
        }
    }
}));

