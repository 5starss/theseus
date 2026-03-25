import { create } from 'zustand';
import { stockApi } from '../api/stock';
import type { Stock } from '../api/stock';
import { useSocketStore } from './useSocketStore';

export interface MarketStock extends Stock {
    buyRatio: number;
    sellRatio: number;
    rank: number;
}

interface MarketUpdate {
    topic: string;
    data: MarketStock[];
}

interface MarketState {
    stocks: Record<string, MarketStock>;
    isConnecting: boolean;
    connectMarketStream: () => Promise<void>;
    disconnectMarketStream: () => void;
    // 수신한 데이터를 처리하는 내부 함수
    handleWsMessage: (event: Event) => void;
}

// Zustand 스토어 생성
export const useMarketStore = create<MarketState>((set, get) => ({
    stocks: {},
    isConnecting: false,

    handleWsMessage: (event: Event) => {
        const customEvent = event as CustomEvent<string>;
        const rawData = customEvent.detail;
        if (!rawData) return;

        try {
            const data: MarketUpdate = JSON.parse(rawData);
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
        // 이미 연결 중이거나 데이터가 이미 존재한다면 중복 실행 방지
        if (get().isConnecting || Object.keys(get().stocks).length > 0) {
            console.log('Market Stream is already active or connecting. Skipping...');
            return;
        }

        console.log('Connecting Market Stream via Singleton...');
        set({ isConnecting: true });

        // 1. 초기 데이터 가져오기
        try {
            const initialStocksList = await stockApi.getTopStocks(100, 'VOLUME');
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
        window.removeEventListener('ws-message', get().handleWsMessage); // 중복 등록 방지
        window.addEventListener('ws-message', get().handleWsMessage);
    },

    disconnectMarketStream: () => {
        console.log('Disconnecting Market Stream (Unsubscribe)...');
        useSocketStore.getState().unsubscribe('HOME_40');
        window.removeEventListener('ws-message', get().handleWsMessage);
    }
}));
