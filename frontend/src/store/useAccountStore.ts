import { create } from 'zustand';
import { accountApi } from '../api/account';
import { orderApi, type PendingOrder, type OrderHistory as ApiOrderHistory } from '../api/order';
import { positionApi } from '../api/position';

export interface PortfolioItem {
    code: string;
    name: string;
    shares: number;
    avgPrice: number;
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
    totalInvested: number;
    cashBalance: number;

    // Portfolio
    portfolio: PortfolioItem[];

    // History
    transactions: Transaction[];
    orders: Order[];

    // Actions
    fetchBalance: () => Promise<void>;
    fetchPositions: () => Promise<void>;
    fetchOrders: (params?: { page?: number; size?: number; status?: string; ticker?: string; yearMonth?: string }) => Promise<void>;
    cancelOrder: (orderId: number | string) => Promise<void>;
    executeTrade: (trade: { stockName: string; stockCode: string; quantity: number; price: number; type: 'buy' | 'sell' }) => void;
}

export const useAccountStore = create<AccountState>((set) => ({
    totalAssets: 0,
    totalInvested: 0,
    cashBalance: 0,
    portfolio: [],
    transactions: [],
    orders: [],

    // 총 예수금, 주문 가능 금액을 가져오는 함수
    fetchBalance: async () => {
        try {
            const balance = await accountApi.getBalance();
            set({
                // dncaTotAmt: 총 예수금, availableAmt: 주문 가능 금액
                // 기존 totalAssets는 총 자산(예수금+투자금)이나 우선 예수금 총액으로 업데이트
                totalAssets: Number(balance.dncaTotAmt),
                cashBalance: Number(balance.availableAmt),
            });
        } catch (error) {
            console.error('Failed to fetch balance in store:', error);
        }
    },

    // 보유 종목 정보를 가져오는 함수
    fetchPositions: async () => {
        try {
            const positions = await positionApi.getPositions();
            const portfolio: PortfolioItem[] = positions.map(p => ({
                code: p.ticker,
                name: p.companyName,
                shares: p.quantity,
                avgPrice: p.averagePrice
            }));
            set({ portfolio });
        } catch (error) {
            console.error('Failed to fetch positions in store:', error);
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

