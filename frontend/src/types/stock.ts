import type { Time } from "lightweight-charts";

// 주식 캔들 (차트용) 데이터 타입 - 모든 수치 필드를 확실히 number로 고정
export interface Candle {
    time: Time;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    value?: number;
}

// 주식 현재가 스냅샷 (API 응답용)
export interface TickSnapshot {
    ticker: string;
    name: string;
    currentPrice: number;
    prevClose: number;
    priceChange: number;
    changeRate: number;
    tradeVol: number;
}

// 주식 호가 데이터 타입
export interface Orderbook {
    ticker: string;
    name?: string;
    askPrice1: number;
    askVolume1: number;
    bidPrice1: number;
    bidVolume1: number;
}

// 실시간 WebSocket 메시지 타입
export interface StockStreamMessage<T = any> {
    topic: 'TICK' | 'ORDERBOOK';
    data: T;
}
