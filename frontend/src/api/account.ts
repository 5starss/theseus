import api from './client';
import type { ApiResponse } from './client';

export interface AccountBalance {
    dncaTotAmt: number;    // 총 예수금
    lockedAmt: number;     // 묶인 금액 (미체결 주문 등)
    availableAmt: number;  // 출금/주문 가능 금액
}

export interface HistoryItem {
    historyId: number;
    transactionType: 'DEPOSIT' | 'WITHDRAWAL' | 'BUY' | 'SELL';
    executedAt: string;
    ticker: string;
    stockName: string;
    quantity: number;
    price: number;
    amount: number;
    balanceAfter: number;
}

export interface AccountHistoryResponse {
    year: number;
    month: number;
    histories: {
        content: HistoryItem[];
        totalPages: number;
        totalElements: number;
        size: number;
        number: number;
    };
}

export const accountApi = {
    // 백엔드 명세: GET /api/v1/core/accounts/balance
    getBalance: async (): Promise<AccountBalance> => {
        try {
            const response = await api.get<ApiResponse<AccountBalance>>('/api/v1/core/accounts/balance');
            if (response.data.isSuccess && response.data.result) {
                return response.data.result;
            }
            throw new Error(response.data.message || 'Failed to fetch balance');
        } catch (error) {
            console.error('Error fetching balance:', error);
            throw error;
        }
    },

    // 백엔드 명세: GET /api/v1/core/accounts/history
    getHistory: async (params?: { year?: number; month?: number; page?: number; size?: number }): Promise<AccountHistoryResponse> => {
        try {
            const response = await api.get<ApiResponse<AccountHistoryResponse>>('/api/v1/core/accounts/history', {
                params
            });
            if (response.data.isSuccess && response.data.result) {
                return response.data.result;
            }
            throw new Error(response.data.message || 'Failed to fetch history');
        } catch (error) {
            console.error('Error fetching account history:', error);
            throw error;
        }
    }
};
