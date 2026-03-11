import api from './client';
import type { ApiResponse } from './client';

export interface AccountBalance {
    dncaTotAmt: number;    // 총 예수금
    lockedAmt: number;     // 묶인 금액 (미체결 주문 등)
    availableAmt: number;  // 출금/주문 가능 금액
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
    }
};
