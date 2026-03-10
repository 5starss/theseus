import axios from 'axios';
import type { ApiResponse } from './stock';

export interface PositionResponse {
    ticker: string;
    quantity: number;
    lockedQuantity: number;
    availableQuantity: number;
    averagePrice: number;
    totalPurchaseAmount: number;
    companyName: string;
}

const api = axios.create({
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true,
});

export const positionApi = {
    // 백엔드 명세: GET /api/v1/core/positions
    getPositions: async (): Promise<PositionResponse[]> => {
        try {
            const response = await api.get<ApiResponse<PositionResponse[]>>('/api/v1/core/positions');
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
