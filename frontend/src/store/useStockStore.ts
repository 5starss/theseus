import { create } from 'zustand';
import { stockApi } from '../api/stock';

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
    "005930": { name: "삼성전자", price: 74500 },
    "000660": { name: "SK하이닉스", price: 162300 },
    "373220": { name: "LG에너지솔루션", price: 401000 },
    "207940": { name: "삼성바이오로직스", price: 812000 },
    "005380": { name: "현대차", price: 236000 },
    "000270": { name: "기아", price: 114500 },
    "068270": { name: "셀트리온", price: 178900 },
    "005490": { name: "POSCO홀딩스", price: 395000 },
    "035420": { name: "NAVER", price: 194500 },
    "051910": { name: "LG화학", price: 450000 },
    "028260": { name: "삼성물산", price: 153200 },
    "012330": { name: "현대모비스", price: 245000 },
    "105560": { name: "KB금융", price: 68100 },
    "055550": { name: "신한지주", price: 47200 },
    "032830": { name: "삼성생명", price: 92300 },
    "003670": { name: "포스코퓨처엠", price: 312500 },
    "035720": { name: "카카오", price: 54200 },
    "066570": { name: "LG전자", price: 98100 },
    "323410": { name: "카카오뱅크", price: 27100 },
    "015760": { name: "한국전력", price: 22400 },
    "000810": { name: "삼성화재", price: 298000 },
    "316140": { name: "우리금융지주", price: 14200 },
    "024110": { name: "기업은행", price: 11950 },
    "011200": { name: "HMM", price: 18150 },
    "010130": { name: "고려아연", price: 452000 },
    "033780": { name: "KT&G", price: 92100 },
    "086280": { name: "현대글로비스", price: 187200 },
    "017670": { name: "SK텔레콤", price: 52100 },
    "009150": { name: "삼성전기", price: 145200 },
    "259960": { name: "크래프톤", price: 241000 },
    "034020": { name: "두산에너빌리티", price: 16100 },
    "036570": { name: "엔씨소프트", price: 198200 },
    "018260": { name: "삼성SDS", price: 152000 },
    "042700": { name: "한미반도체", price: 141500 },
    "010140": { name: "삼성중공업", price: 8210 },
    "011170": { name: "롯데케미칼", price: 122500 },
    "267250": { name: "HD현대", price: 68200 },
    "090430": { name: "아모레퍼시픽", price: 128500 },
    "003490": { name: "대한항공", price: 21900 },
    "051900": { name: "LG생활건강", price: 341000 },
};

// 실제 WebSocket 연결 혹은 fallback 시뮬레이션을 위한 타이머
let stockInterval: ReturnType<typeof setInterval> | null = null;
let stockWs: WebSocket | null = null;

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

    // 주식 상세 페이지에서 WebSocket 스트림을 연결하는 함수 (실패 시 시뮬레이션 fallback)
    connectStockStream: (code) => {
        // 기존 연결 정리
        if (stockWs) {
            stockWs.close();
            stockWs = null;
        }
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

        console.log(`Starting Dashboard Stream [${code}]...`);

        // 0. 초기 호가 데이터(Snapshot) 가져오기
        stockApi.getOrderbook(code).then(obData => {
            set({
                askPrice: obData.askPrice1, // 1매수호가
                askVolume: obData.askVolume1,  // 1매수호가 잔량
                bidPrice: obData.bidPrice1, // 1매도호가
                bidVolume: obData.bidVolume1, // 1매도호가 잔량
                currentPrice: obData.currentPrice, // 현재가
            });
        });

        // 1. Fallback: 웹소켓 연결 성공 전까지 혹은 백엔드 에러 시 동작할 모의 데이터 인터벌 발생기
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
        }, 200);

        // 2. 실제 WebSocket 연결
        try {
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${window.location.host}/v1/stocks/ws`;
            stockWs = new WebSocket(wsUrl);

            stockWs.onopen = () => {
                console.log(`Connected to Dashboard WebSocket [${code}]`);
                // 백엔드 연결 성공 시 Fallback용 모의 인터벌 제거
                if (stockInterval) {
                    clearInterval(stockInterval);
                    stockInterval = null;
                }

                // 구독 요청 전송
                stockWs?.send(JSON.stringify({ action: 'SUBSCRIBE', topic: 'TICK', ticker: code }));
                stockWs?.send(JSON.stringify({ action: 'SUBSCRIBE', topic: 'ORDERBOOK', ticker: code }));
            };

            stockWs.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.topic === `TICK:${code}` && data.data) {
                        const tickData = data.data; // domain.Stock 호환
                        set((state) => ({
                            currentPrice: tickData.currentPrice,
                            priceChange: tickData.currentPrice - state.prevClose,
                            changeRate: tickData.changeRate || ((tickData.currentPrice - state.prevClose) / state.prevClose) * 100,
                        }));
                    } else if (data.topic === `ORDERBOOK:${code}` && data.data) {
                        const obData = data.data; // domain.OrderbookResponse 호환
                        set({
                            askPrice: obData.askPrice1,
                            askVolume: obData.askVolume1,
                            bidPrice: obData.bidPrice1,
                            bidVolume: obData.bidVolume1,
                        });
                    }
                } catch (e) {
                    console.error("Failed to parse stock websocket message", e);
                }
            };

            stockWs.onclose = () => {
                console.log('Dashboard WebSocket disconnected');
                stockWs = null;
            };

            stockWs.onerror = (error) => {
                console.error('Dashboard WebSocket error (using fallback):', error);
                stockWs?.close();
            };
        } catch (error) {
            console.error('Failed to initialize WebSocket:', error);
        }
    },

    // 스트림 정리 함수 (컴포넌트 언마운트 시 호출)
    disconnectStockStream: () => {
        if (stockWs) {
            if (stockWs.readyState === WebSocket.OPEN) {
                stockWs.send(JSON.stringify({ action: 'UNSUBSCRIBE', topic: 'TICK', ticker: useStockStore.getState().stockCode }));
                stockWs.send(JSON.stringify({ action: 'UNSUBSCRIBE', topic: 'ORDERBOOK', ticker: useStockStore.getState().stockCode }));
            }
            stockWs.close();
            stockWs = null;
        }
        if (stockInterval) {
            clearInterval(stockInterval);
            stockInterval = null;
            console.log('Disconnected Dashboard Mock Fallback WebSockets');
        }
        console.log('Dashboard WebSocket stream cleaned up');
    }
}));
