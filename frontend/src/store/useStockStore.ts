import { create } from 'zustand';

// 주식 호가 및 거래 관련 전역 상태 타입
interface StockState {
    stockCode: string;
    stockName: string;

    currentPrice: number;
    priceChange: number;
    changeRate: number;

    askPrice: number;
    askVolume: number;
    bidPrice: number;
    bidVolume: number;

    prevClose: number; // 전일 종가

    setStock: (code: string) => void;
    setCurrentPrice: (price: number) => void;
    updateOrderbook: (ask: { price: number; volume: number }, bid: { price: number; volume: number }) => void;
    connectStockStream: (code: string) => void;
    disconnectStockStream: () => void;
}

// Mock database
export const MOCK_STOCKS: Record<string, { name: string; price: number }> = {
    '005930': { name: '삼성전자', price: 214500 },
    '000660': { name: 'SK하이닉스', price: 1037000 },
    '122630': { name: 'KODEX 레버리지', price: 108470 },
    '042700': { name: '한미반도체', price: 241500 },
    '005380': { name: '현대차', price: 257000 },
    '035720': { name: '카카오', price: 54200 },
    '035420': { name: 'NAVER', price: 198000 },
    '373220': { name: 'LG에너지솔루션', price: 412000 },
    '068270': { name: '셀트리온', price: 187000 },
    '005490': { name: 'POSCO홀딩스', price: 382000 },
};

// 실제 WebSocket 연결이 아니므로, setInterval을 사용하여 주식 데이터를 주기적으로 업데이트하는 방식
let stockInterval: ReturnType<typeof setInterval> | null = null;

export const useStockStore = create<StockState>((set) => ({
    stockCode: '005930',
    stockName: '삼성전자',
    currentPrice: 214500,
    prevClose: 203500,
    priceChange: 11000,
    changeRate: 5.40,

    askPrice: 215000,
    askVolume: 10537,
    bidPrice: 214500,
    bidVolume: 2593,

    // 주식 코드로 초기 데이터 설정
    setStock: (code) =>
        set(() => {
            const stockInfo = MOCK_STOCKS[code] || { name: '알 수 없음', price: 50000 };
            const pseudoPrevClose = Math.round(stockInfo.price * 0.95); // 임의의 전일 종가
            const priceChange = stockInfo.price - pseudoPrevClose;
            const changeRate = (priceChange / pseudoPrevClose) * 100;
            return {
                stockCode: code,
                stockName: stockInfo.name,
                currentPrice: stockInfo.price,
                prevClose: pseudoPrevClose,
                priceChange,
                changeRate,
                askPrice: stockInfo.price + 500,
                bidPrice: stockInfo.price,
            };
        }),
    
    // 현재가 업데이트 시, 가격 변화량과 등락률도 함께 계산하여 상태 업데이트
    setCurrentPrice: (price) =>
        set((state) => ({
            currentPrice: price,
            priceChange: price - state.prevClose,
            changeRate: ((price - state.prevClose) / state.prevClose) * 100,
        })),
    
    // 호가 업데이트 시, ask/bid 가격과 거래량을 함께 업데이트
    updateOrderbook: (ask, bid) =>
        set({
            askPrice: ask.price,
            askVolume: ask.volume,
            bidPrice: bid.price,
            bidVolume: bid.volume,
        }),
    
    // 주식 상세 페이지에서 WebSocket 스트림을 시뮬레이션하여 가격과 호가 정보를 주기적으로 업데이트하는 함수
    connectStockStream: (code) => {
        if (stockInterval) {
            clearInterval(stockInterval);
            stockInterval = null;
        }

        // 초기 주식 정보 설정
        set(() => {
            const stockInfo = MOCK_STOCKS[code] || { name: '알 수 없음', price: 50000 };
            const pseudoPrevClose = Math.round(stockInfo.price * 0.95);
            const priceChange = stockInfo.price - pseudoPrevClose;
            const changeRate = (priceChange / pseudoPrevClose) * 100;
            return {
                stockCode: code,
                stockName: stockInfo.name,
                currentPrice: stockInfo.price,
                prevClose: pseudoPrevClose,
                priceChange,
                changeRate,
                askPrice: stockInfo.price + 500,
                bidPrice: stockInfo.price,
            };
        });

        console.log(`Connecting to Mock WebSockets for Dashbard [${code}]...`);

        // Start streaming data(랜덤 가격 변동과 호가 업데이트 시뮬레이션)
        stockInterval = setInterval(() => {
            set((state) => {
                const diff = Math.floor(Math.random() * 3) * 100 - 100;
                const newPrice = Math.max(0, state.currentPrice + diff);

                return {
                    currentPrice: newPrice,
                    priceChange: newPrice - state.prevClose,
                    changeRate: ((newPrice - state.prevClose) / state.prevClose) * 100,
                    askPrice: newPrice + 100,
                    askVolume: Math.floor(Math.random() * 14000) + 1000,
                    bidPrice: newPrice,
                    bidVolume: Math.floor(Math.random() * 14000) + 1000,
                };
            });
        }, 200); // 200ms마다 업데이트 (실제 환경에서는 WebSocket 메시지 수신 시마다 업데이트)
    },

    // 스트림 정리 함수 (컴포넌트 언마운트 시 호출)
    disconnectStockStream: () => {
        if (stockInterval) {
            clearInterval(stockInterval);
            stockInterval = null;
            console.log('Disconnected Dashboard Mock WebSockets');
        }
    }
}));
