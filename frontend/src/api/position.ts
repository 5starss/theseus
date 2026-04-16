import api from './client';
import type { ApiResponse } from './client';
import type { AccountType } from './account';

export interface PositionResponse {
    ticker: string;
    quantity: number;
    lockedQuantity: number;
    availableQuantity: number;
    averagePrice: number;
    totalPurchaseAmount: number;
    companyName: string;
}

export const positionApi = {
    // 백엔드 명세: GET /api/v1/core/positions?account_type=USER
    getPositions: async (accountType: AccountType = 'USER'): Promise<PositionResponse[]> => {
        try {
            const response = await api.get<ApiResponse<PositionResponse[]>>('/api/v1/core/positions', {
                params: { account_type: accountType }
            });
            if (response.data.isSuccess && response.data.result) {
                return response.data.result;
            }
            throw new Error(response.data.message || 'Failed to fetch positions');
        } catch (error) {
            console.error('Error fetching positions:', error);
            throw error;
        }
    }
};
