import { create } from 'zustand';

import { stockApi } from '../api/stock';
import type { Stock } from '../api/stock';

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
}

// 이 변수는 컴포넌트가 마운트될 때 스트림을 시작하고 언마운트될 때 스트림을 정리하는 데 사용
let marketWs: WebSocket | null = null;

// Zustand 스토어 생성
export const useMarketStore = create<MarketState>((set) => ({
    stocks: {},
    isConnecting: false,

    connectMarketStream: async () => {
        if (marketWs && marketWs.readyState === WebSocket.OPEN) return; // 이미 연결되어 있으면 무시

        console.log('Fetching Top Stocks and Connecting WebSockets...');
        set({ isConnecting: true });

        // 1. API(또는 더미)에서 40개 목록 받아오기 (백엔드는 HOME_40)
        const initialStocksList = await stockApi.getTopStocks(40, 'VOLUME');
        const initialStocksMap: Record<string, MarketStock> = {};

        initialStocksList.forEach((stock, index) => {
            initialStocksMap[stock.ticker] = {
                ...stock,
                buyRatio: Math.floor(Math.random() * 60) + 20,
                sellRatio: Math.floor(Math.random() * 60) + 20,
                rank: index + 1 // 정렬되어 오므로 그대로 순위 지정
            };
        });

        set({ stocks: initialStocksMap, isConnecting: false });

        // 2. WebSocket 연결
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/v1/stocks/ws`;

        marketWs = new WebSocket(wsUrl);

        marketWs.onopen = () => {
            console.log('Connected to Market WebSocket');
            // 구독 요청 전송
            marketWs?.send(JSON.stringify({ action: 'SUBSCRIBE', topic: 'HOME_40' }));
        };

        marketWs.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                // HOME_40 토픽의 메시지 처리
                if (data.topic === 'HOME_40' && Array.isArray(data.data)) {
                    set((state) => {
                        const newStocks = { ...state.stocks };
                        data.data.forEach((stock: any, index: number) => {
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
                console.error("Failed to parse websocket message", e);
            }
        };

        marketWs.onclose = () => {
            console.log('Market WebSocket disconnected');
            marketWs = null;
        };

        marketWs.onerror = (error) => {
            console.error('Market WebSocket error:', error);
            marketWs?.close();
        };
    },

    disconnectMarketStream: () => {
        if (marketWs) {
            if (marketWs.readyState === WebSocket.OPEN) {
                marketWs.send(JSON.stringify({ action: 'UNSUBSCRIBE', topic: 'HOME_40' }));
            }
            marketWs.close();
            marketWs = null;
            console.log('Disconnected Market WebSockets');
            set({ isConnecting: false });
        }
    }
}));
