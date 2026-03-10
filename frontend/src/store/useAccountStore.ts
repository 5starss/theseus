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
    stockName: string;
    type: 'buy' | 'sell';
    status: 'completed' | 'canceled' | 'pending';
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

// Initial Mock Data
const MOCK_PORTFOLIO: PortfolioItem[] = [
    { code: '005930', name: '삼성전자', shares: 120, avgPrice: 65000 },
    { code: '000660', name: 'SK하이닉스', shares: 45, avgPrice: 120000 },
    { code: '035420', name: 'NAVER', shares: 80, avgPrice: 185000 },
];

const MOCK_TRANSACTIONS: Transaction[] = [
    { id: 't1', date: '2.25', time: '00:27', type: 'buy', amount: -185100, remainingBalance: 247816, description: '삼성전자 1주', stockName: '삼성전자', quantity: 1 },
    { id: 't2', date: '2.25', time: '00:27', type: 'buy', amount: -44910, remainingBalance: 432916, description: 'KODEX 미국S&P500 2주', stockName: 'KODEX 미국S&P500', quantity: 2 },
    { id: 't3', date: '2.25', time: '00:27', type: 'buy', amount: -176070, remainingBalance: 477826, description: 'KODEX 200 2주', stockName: 'KODEX 200', quantity: 2 },
    { id: 't4', date: '2.24', time: '00:23', type: 'buy', amount: -30865, remainingBalance: 653896, description: '휴림로봇 2주', stockName: '휴림로봇', quantity: 2 },
    { id: 't5', date: '2.23', time: '00:29', type: 'buy', amount: -45250, remainingBalance: 684761, description: '한화솔루션 1주', stockName: '한화솔루션', quantity: 1 },
    { id: 't6', date: '2.23', time: '00:29', type: 'buy', amount: -168720, remainingBalance: 730011, description: '한미반도체 1주', stockName: '한미반도체', quantity: 1 },
    { id: 't7', date: '2.13', time: '00:21', type: 'buy', amount: -171000, remainingBalance: 898731, description: '삼성전자 1주', stockName: '삼성전자', quantity: 1 },
    { id: 't8', date: '2.11', time: '00:26', type: 'buy', amount: -46080, remainingBalance: 1069731, description: 'KODEX 미국S&P500 2주', stockName: 'KODEX 미국S&P500', quantity: 2 },
    { id: 't9', date: '2.11', time: '00:26', type: 'buy', amount: -157270, remainingBalance: 1116811, description: '기아 1주', stockName: '기아', quantity: 1 },
];

const MOCK_ORDERS: Order[] = [
    { id: 'o_pending1', date: '2.25', stockName: 'NAVER', type: 'buy', status: 'pending', quantity: 1, price: 185000 },
    { id: 'o_pending2', date: '2.25', stockName: '카카오', type: 'sell', status: 'pending', quantity: 2, price: 110000 },
    { id: 'o1', date: '2.22', stockName: 'KODEX 200', type: 'buy', status: 'completed', quantity: 2, price: 176070 },
    { id: 'o2', date: '2.22', stockName: 'KODEX 미국S&P500', type: 'buy', status: 'completed', quantity: 2, price: 22455 },
    { id: 'o3', date: '2.22', stockName: '삼성전자', type: 'buy', status: 'completed', quantity: 1, price: 185100 },
    { id: 'o4', date: '2.20', stockName: '휴림로봇', type: 'buy', status: 'completed', quantity: 2, price: 30865 },
    { id: 'o5', date: '2.19', stockName: '한미반도체', type: 'buy', status: 'completed', quantity: 1, price: 168720 },
    { id: 'o6', date: '2.19', stockName: '한화솔루션', type: 'buy', status: 'completed', quantity: 1, price: 45250 },
    { id: 'o7', date: '2.11', stockName: '삼성전자', type: 'buy', status: 'completed', quantity: 1, price: 171000 },
    { id: 'o8', date: '2.11', stockName: '삼성전자', type: 'buy', status: 'canceled', quantity: 1, price: 171000 },
    { id: 'o9', date: '2.9', stockName: '기아', type: 'buy', status: 'completed', quantity: 1, price: 157270 },
];

export const useAccountStore = create<AccountState>((set) => ({
    totalAssets: 48500200,
    totalInvested: 28000000,
    cashBalance: 20500200,
    portfolio: MOCK_PORTFOLIO,
    transactions: MOCK_TRANSACTIONS,
    orders: MOCK_ORDERS,
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
                stockName: po.companyName,
                type: po.orderType.toLowerCase() as 'buy' | 'sell',
                status: 'pending',
                quantity: po.unexecutedQuantity,
                price: po.totalPrice / po.unexecutedQuantity
            }));

            const transformedCompleted: Order[] = data.completed.content.map((oh: ApiOrderHistory) => ({
                id: oh.historyId.toString(),
                date: transformDate(oh.createdAt),
                stockName: oh.companyName,
                type: oh.orderType.toLowerCase() as 'buy' | 'sell',
                status: oh.historyType === 'TRADE' ? 'completed' : 'canceled',
                quantity: oh.quantity,
                price: oh.price
            }));

            set({ orders: [...transformedPending, ...transformedCompleted] });
        } catch (error) {
            console.error('Failed to fetch orders in store:', error);
        }
    },
    cancelOrder: async (orderId) => {
        try {
            await orderApi.cancelOrder(orderId);
            const getBalance = useAccountStore.getState().fetchBalance;
            const getOrders = useAccountStore.getState().fetchOrders;
            await Promise.all([getBalance(), getOrders()]);
        } catch (error) {
            console.error('Failed to cancel order in store:', error);
        }
    },
    executeTrade: (trade) => set((state) => {
        const { stockName, stockCode, quantity, price, type } = trade;
        const totalAmount = quantity * price;
        const newCashBalance = type === 'buy' ? state.cashBalance - totalAmount : state.cashBalance + totalAmount;

        // Update portfolio
        const newPortfolio = [...state.portfolio];
        const existingItemIndex = newPortfolio.findIndex(item => item.name === stockName);

        if (type === 'buy') {
            if (existingItemIndex >= 0) {
                const existing = newPortfolio[existingItemIndex];
                const newShares = existing.shares + quantity;
                const newAvgPrice = ((existing.shares * existing.avgPrice) + totalAmount) / newShares;
                newPortfolio[existingItemIndex] = { ...existing, shares: newShares, avgPrice: newAvgPrice };
            } else {
                newPortfolio.push({ code: stockCode, name: stockName, shares: quantity, avgPrice: price });
            }
        } else { // sell
            if (existingItemIndex >= 0) {
                const existing = newPortfolio[existingItemIndex];
                const newShares = existing.shares - quantity;
                if (newShares <= 0) {
                    newPortfolio.splice(existingItemIndex, 1);
                } else {
                    newPortfolio[existingItemIndex] = { ...existing, shares: newShares };
                }
            }
        }

        // Add to orders
        const newOrder: Order = {
            id: `o${Date.now()}`,
            date: new Date().toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' }).replace('/', '.'),
            stockName,
            type,
            status: 'completed',
            quantity,
            price
        };

        return {
            cashBalance: newCashBalance,
            portfolio: newPortfolio,
            orders: [newOrder, ...state.orders]
        };
    })
}));
