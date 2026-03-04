import { create } from 'zustand';
import { MOCK_STOCKS } from './useStockStore';

export interface MarketStock {
    code: string;
    name: string;
    price: number;
    changeRate: number;
    volume: number;
    buyRatio: number;
    sellRatio: number;
    rank: number;
}

interface MarketState {
    stocks: Record<string, MarketStock>;
    isConnecting: boolean;
    connectMarketStream: () => void;
    disconnectMarketStream: () => void;
}

// 초기 주식 데이터 설정 (MOCK_STOCKS 기반으로 MarketStock 형태로 변환)
const INITIAL_STOCKS: Record<string, MarketStock> = {};
let initialRank = 1;
Object.entries(MOCK_STOCKS).forEach(([code, stock]) => {
    INITIAL_STOCKS[code] = {
        code,
        name: stock.name,
        price: stock.price,
        changeRate: parseFloat((Math.random() * 10 - 5).toFixed(2)),
        volume: Math.floor(Math.random() * 1000) + 100,
        buyRatio: Math.floor(Math.random() * 60) + 20,
        sellRatio: Math.floor(Math.random() * 60) + 20,
        rank: initialRank++,
    };
});

// 실제 WebSocket 연결이 아니므로, setInterval을 사용하여 주식 데이터를 주기적으로 업데이트하는 방식으로 시뮬레이션. 
// 이 변수는 컴포넌트가 마운트될 때 스트림을 시작하고 언마운트될 때 스트림을 정리하는 데 사용
let marketInterval: ReturnType<typeof setInterval> | null = null;

// Zustand 스토어 생성
export const useMarketStore = create<MarketState>((set) => ({
    stocks: INITIAL_STOCKS,
    isConnecting: false,

    connectMarketStream: () => {
        if (marketInterval) return; // 이미 연결되어 있으면 무시

        console.log('Connecting to Mock WebSockets for Market Data...');
        set({ isConnecting: true });

        // Start streaming data(랜덤 가격 변동과 거래량 업데이트 시뮬레이션)
        marketInterval = setInterval(() => {
            set((state) => {
                const newStocks = { ...state.stocks };

                // 랜덤하게 1~4개의 종목을 선택하여 가격과 거래량 업데이트 시뮬레이션
                const codes = Object.keys(newStocks);
                const updatesCount = Math.floor(Math.random() * 4) + 1; // 1~4개 종목 업데이트

                for (let i = 0; i < updatesCount; i++) {
                    const code = codes[Math.floor(Math.random() * codes.length)];
                    const stock = newStocks[code];

                    const priceDiff = Math.floor(Math.random() * 3) * 100 - 100; // -100, 0, or 100
                    const newPrice = Math.max(0, stock.price + priceDiff);
                    const newChangeRate = stock.changeRate + (priceDiff / stock.price) * 100;
                    const newVolume = stock.volume + Math.floor(Math.random() * 5); // 거래량은 조금씩 증가

                    newStocks[code] = {
                        ...stock,
                        price: newPrice,
                        changeRate: parseFloat(newChangeRate.toFixed(2)),
                        volume: newVolume,
                        // 매수/매도 비율도 랜덤하게 조금씩 변화시키되, 10%~90% 범위로 유지
                        buyRatio: Math.floor(Math.max(10, Math.min(90, stock.buyRatio + (Math.random() * 6 - 3)))),
                        sellRatio: Math.floor(Math.max(10, Math.min(90, stock.sellRatio + (Math.random() * 6 - 3)))),
                    };
                }

                return { stocks: newStocks }; // 상태 업데이트는 전체 stocks 객체를 새로 만들어서 반환하여, Zustand가 변경을 감지할 수 있도록 함
            });
        }, 500); // 500ms마다 업데이트 (실제 환경에서는 WebSocket 메시지 수신 시마다 업데이트)
    },

    disconnectMarketStream: () => {
        if (marketInterval) {
            clearInterval(marketInterval);
            marketInterval = null;
            console.log('Disconnected from Mock WebSockets');
            set({ isConnecting: false });
        }
    }
}));
