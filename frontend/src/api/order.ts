import api from './client';
import type { ApiResponse } from './client';
import type { AccountType } from './account';

export interface PageResponse<T> {
    content: T[];
    page: number;
    size: number;
    totalElements: number;
    totalPages: number;
    last: boolean;
}

export interface PendingOrder {
    orderId: number;
    ticker: string;
    companyName: string;
    orderType: 'BUY' | 'SELL';
    status: string;
    totalPrice: number;
    unexecutedQuantity: number;
    createdAt: string;
}

export interface OrderHistory {
    historyId: number;
    orderId: number;
    ticker: string;
    companyName: string;
    orderType: 'BUY' | 'SELL';
    historyType: 'EXECUTION' | 'CANCELLATION' | 'SYSTEM_CANCELLATION';
    price: number;
    quantity: number;
    totalPrice: number;
    createdAt: string;
}

export interface OrderHistoryResponse {
    pending: PageResponse<PendingOrder>;
    completed: PageResponse<OrderHistory>;
}

export interface OrderDetailResponse {
    orderId: number;
    companyName: string;
    ticker: string;
    orderType: 'BUY' | 'SELL';
    status: string;
    priceType: 'LIMIT' | 'MARKET';
    pricePerShare: number;
    orderQuantity: number;
    orderAmount: number;
    orderCreatedAt: string;
}

export interface OrderHistoryDetailResponse {
    historyId: number;
    orderId: number;
    companyName: string;
    ticker: string;
    orderType: 'BUY' | 'SELL';
    priceType: 'LIMIT' | 'MARKET';
    historyType: 'EXECUTION' | 'CANCELLATION' | 'SYSTEM_CANCELLATION';
    pricePerShare: number;
    quantity: number;
    totalAmount: number;
    orderCreatedAt: string;
    createdAt: string; // 체결 또는 취소 시각
}

export interface TradePolicyResponse {
    feeRate: number;
    taxRate: number;
}

export const orderApi = {
    // 백엔드 명세: GET /api/v1/core/orders/trade-policy (인증 불필요)
    getTradePolicy: async (): Promise<TradePolicyResponse> => {
        try {
            const response = await api.get<ApiResponse<TradePolicyResponse>>('/api/v1/core/orders/trade-policy');
            if (response.data.isSuccess && response.data.result) {
                return response.data.result;
            }
            throw new Error(response.data.message || 'Failed to fetch trade policy');
        } catch (error) {
            console.error('Error fetching trade policy:', error);
            throw error;
        }
    },

    // 백엔드 명세: POST /api/v1/core/orders
    createOrder: async (data: {
        ticker: string;
        order_type: 'BUY' | 'SELL';
        price_type: 'LIMIT' | 'MARKET';
        price: number;
        quantity: number;
        account_type?: AccountType;
    }): Promise<void> => {
        try {
            const response = await api.post<ApiResponse<void>>('/api/v1/core/orders', {
                account_type: 'USER', // 기본값
                ...data
            });
            if (!response.data.isSuccess) {
                throw new Error(response.data.message || 'Failed to create order');
            }
        } catch (error) {
            console.error('Error creating order:', error);
            throw error;
        }
    },

    // 백엔드 명세: GET /api/v1/core/orders?account_type=USER
    getOrders: async (params: {
        page?: number;
        size?: number;
        status?: string;
        ticker?: string;
        yearMonth?: string;
        account_type?: AccountType;
    } = {}): Promise<OrderHistoryResponse> => {
        try {
            const response = await api.get<ApiResponse<OrderHistoryResponse>>('/api/v1/core/orders', { 
                params: {
                    account_type: 'USER', // 기본값
                    ...params
                } 
            });
            if (response.data.isSuccess && response.data.result) {
                return response.data.result;
            }
            throw new Error(response.data.message || 'Failed to fetch orders');
        } catch (error) {
            console.error('Error fetching orders:', error);
            throw error;
        }
    },

    // 백엔드 명세: POST /api/v1/core/orders/{orderId}/cancel
    cancelOrder: async (orderId: number | string): Promise<void> => {
        try {
            const response = await api.post<ApiResponse<void>>(`/api/v1/core/orders/${orderId}/cancel`);
            if (!response.data.isSuccess) {
                throw new Error(response.data.message || 'Failed to cancel order');
            }
        } catch (error) {
            console.error('Error canceling order:', error);
            throw error;
        }
    },

    // 백엔드 명세: GET /api/v1/core/orders/pending/{orderId}
    getOrderDetail: async (orderId: number | string): Promise<OrderDetailResponse> => {
        try {
            const response = await api.get<ApiResponse<OrderDetailResponse>>(`/api/v1/core/orders/pending/${orderId}`);
            if (response.data.isSuccess && response.data.result) {
                return response.data.result;
            }
            throw new Error(response.data.message || 'Failed to fetch order detail');
        } catch (error) {
            console.error('Error fetching order detail:', error);
            throw error;
        }
    },

    // 백엔드 명세: GET /api/v1/core/orders/completed/{historyId}
    getHistoryDetail: async (historyId: number | string): Promise<OrderHistoryDetailResponse> => {
        try {
            const response = await api.get<ApiResponse<OrderHistoryDetailResponse>>(`/api/v1/core/orders/completed/${historyId}`);
            if (response.data.isSuccess && response.data.result) {
                return response.data.result;
            }
            throw new Error(response.data.message || 'Failed to fetch history detail');
        } catch (error) {
            console.error('Error fetching history detail:', error);
            throw error;
        }
    }
};
