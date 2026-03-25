export type OrderSide = 'BID' | 'ASK'; // 매수(BID), 매도(ASK)
export type OrderStatus = 'PENDING' | 'COMPLETED' | 'CANCELLED' | 'REJECTED';
export type OrderType = 'LIMIT' | 'MARKET';

export interface Order {
    id: number;
    ticker: string;
    name: string;
    price: number;
    quantity: number;
    side: OrderSide;
    status: OrderStatus;
    type: OrderType;
    createdAt: string;
    updatedAt?: string;
    filledQuantity: number;
    remainingQuantity: number;
}

export interface OrderRequest {
    ticker: string;
    price: number;
    quantity: number;
    side: OrderSide;
    type: OrderType;
    accountId: string;
}

export interface OrderResponse {
    orderId: number;
    status: string;
    message?: string;
}
