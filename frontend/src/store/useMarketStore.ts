import { create } from 'zustand';
import { stockApi } from '../api/stock';
import type { Stock } from '../api/stock';
import { useSocketStore } from './useSocketStore';

export interface MarketStock extends Stock {
    buyRatio: number;
    sellRatio: number;
    rank: number;
}

interface MarketState {
    stocks: Record<string, MarketStock>;
    isConnecting: boolean;
    connectMarketStream: () => Promise<void>;
    disconnectMarketStream: () => void;
    // 수신한 데이터를 처리하는 내부 함수
    handleWsMessage: (event: CustomEvent) => void;
}

// Zustand 스토어 생성
export const useMarketStore = create<MarketState>((set, get) => ({
    stocks: {},
    isConnecting: false,

    handleWsMessage: (event: any) => {
        const rawData = event.detail;
        if (!rawData) return;

        try {
            const data = JSON.parse(rawData.toString());
            if (data.topic === 'HOME_40' && Array.isArray(data.data)) {
                set((state) => {
                    const newStocks = { ...state.stocks };
                    data.data.forEach((stock: MarketStock, index: number) => {
                        if (newStocks[stock.ticker]) {
                            newStocks[stock.ticker] = {
                                ...newStocks[stock.ticker],
                                ...stock,
                                rank: index + 1
                            };
                        } else {
                            newStocks[stock.ticker] = {
                                ...stock,
                                buyRatio: Math.floor(Math.random() * 60) + 20,
                                sellRatio: Math.floor(Math.random() * 60) + 20,
                                rank: index + 1
                            };
                        }
                    });
                    return { stocks: newStocks };
                });
            }
        } catch (e) {
            console.error("Failed to parse market websocket segment", e);
        }
    },

    connectMarketStream: async () => {
        console.log('Connecting Market Stream via Singleton...');
        set({ isConnecting: true });

        // 1. 초기 데이터 가져오기
        try {
            const initialStocksList = await stockApi.getTopStocks(20, 'VOLUME');
            const initialStocksMap: Record<string, MarketStock> = {};

            initialStocksList.forEach((stock, index) => {
                initialStocksMap[stock.ticker] = {
                    ...stock,
                    buyRatio: Math.floor(Math.random() * 60) + 20,
                    sellRatio: Math.floor(Math.random() * 60) + 20,
                    rank: index + 1
                };
            });

            set({ stocks: initialStocksMap, isConnecting: false });
        } catch (err) {
            console.error("Failed to fetch top stocks", err);
            set({ isConnecting: false });
        }

        // 2. 싱글톤 구독 설정
        useSocketStore.getState().subscribe('HOME_40');

        // 3. 메시지 핸들러 등록
        window.addEventListener('ws-message' as any, get().handleWsMessage);
    },

    disconnectMarketStream: () => {
        console.log('Disconnecting Market Stream (Unsubscribe)...');
        useSocketStore.getState().unsubscribe('HOME_40');
        window.removeEventListener('ws-message' as any, get().handleWsMessage);
    }
}));
