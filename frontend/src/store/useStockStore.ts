import { create } from 'zustand';
import { stockApi } from '../api/stock';
import { useAuthStore } from './useAuthStore';

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
let stockTimeout: ReturnType<typeof setTimeout> | null = null;

export const useStockStore = create<StockState>((set) => ({
    stockCode: '',
    stockName: '',
    currentPrice: 0,
    prevClose: 0,
    priceChange: 0,
    changeRate: 0,

    askPrice: 0,
    askVolume: 0,
    bidPrice: 0,
    bidVolume: 0,

    // 주식 코드로 초기 데이터 설정
    setStock: (code) =>
        set({
            stockCode: code,
            stockName: '-',
            currentPrice: 0,
            prevClose: 0,
            priceChange: 0,
            changeRate: 0,
            askPrice: 0,
            askVolume: 0,
            bidPrice: 0,
            bidVolume: 0,
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
        // 즉시 stockCode 설정 (다른 컴포넌트 관찰용)
        set({ stockCode: code });

        // 기존 연결 정리
        if (stockWs) {
            stockWs.close();
            stockWs = null;
        }
        if (stockInterval) {
            clearInterval(stockInterval);
            stockInterval = null;
        }
        if (stockTimeout) {
            clearTimeout(stockTimeout);
            stockTimeout = null;
        }

        // 초기 데이터 로딩
        console.log(`Starting Dashboard Stream [${code}]...`);

        // 0. 초기 틱 데이터(Snapshot) 가져오기 (비로그인 상태에서도 현재가 확인 가능)
        stockApi.getTickSnapshot(code).then(tickData => {
            if (tickData) {
                const currentPrice = tickData.currentPrice;
                const changeRate = tickData.changeRate;
                const prevClose = Math.round(currentPrice / (1 + (changeRate / 100)));

                set({
                    stockCode: code,
                    stockName: tickData.name,
                    currentPrice: currentPrice,
                    prevClose: prevClose,
                    priceChange: currentPrice - prevClose,
                    changeRate: changeRate,
                    // 호가 정보는 WebSocket 연결 전까지 초기값 유지 또는 Orderbook API 별도 호출 필요 시 추가
                    askPrice: 0,
                    askVolume: 0,
                    bidPrice: 0,
                    bidVolume: 0,
                });
            } else {
                // Tick 샷 실패 시 Orderbook API로 임시 Fallback 시도
                stockApi.getOrderbook(code).then(obData => {
                    const cp = obData.currentPrice;
                    const cr = obData.changeRate;
                    const pc = Math.round(cp / (1 + (cr / 100)));
                    set({
                        stockCode: code,
                        stockName: obData.name,
                        currentPrice: cp,
                        prevClose: pc,
                        priceChange: cp - pc,
                        changeRate: cr,
                        askPrice: obData.askPrice1,
                        askVolume: obData.askVolume1,
                        bidPrice: obData.bidPrice1,
                        bidVolume: obData.bidVolume1,
                    });
                });
            }
        }).catch(err => {
            console.error("Failed to fetch initial tick snapshot", err);
        });

        // 1. 실제 WebSocket 연결 (React StrictMode 연속 렌더링에 의한 소켓 폭주 방지용 딜레이)
        stockTimeout = setTimeout(() => {
            try {
                const token = useAuthStore.getState().token;
                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${wsProtocol}//${window.location.host}/v1/stocks/ws${token ? `?token=${token}` : ''}`;

                stockWs = new WebSocket(wsUrl);

                stockWs.onopen = () => {
                    console.log(`Connected to Dashboard WebSocket [${code}]`);
                    // 구독 요청 전송
                    stockWs?.send(JSON.stringify({ action: 'SUBSCRIBE', topic: 'TICK', ticker: code }));
                    stockWs?.send(JSON.stringify({ action: 'SUBSCRIBE', topic: 'ORDERBOOK', ticker: code }));
                };

                stockWs.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);

                        if (data.topic === "ERROR") {
                            console.warn("WS ERROR Received:", data.data);
                            return;
                        }

                        if (data.topic === "TICK" && data.data && data.data.ticker === code) {
                            const tickData = data.data;
                            console.log("WS TICK data processed:", tickData.price, "Change Rate:", tickData.change_rate);
                            set((state) => {
                                let newPrevClose = state.prevClose;
                                // 스냅샷 실패 시 TICK 데이터를 이용해 기준 가격(전일 종가)을 역산
                                if (newPrevClose === 0 && tickData.change_rate) {
                                    newPrevClose = Math.round(tickData.price / (1 + (tickData.change_rate / 100)));
                                }

                                return {
                                    stockName: state.stockName === '-' && tickData.name ? tickData.name : state.stockName,
                                    currentPrice: tickData.price,
                                    prevClose: newPrevClose,
                                    priceChange: newPrevClose > 0 ? tickData.price - newPrevClose : ((tickData.price - state.prevClose) || 0),
                                    changeRate: tickData.change_rate !== undefined ? tickData.change_rate : (newPrevClose > 0 ? ((tickData.price - newPrevClose) / newPrevClose) * 100 : 0),
                                };
                            });
                        } else if (data.topic === "ORDERBOOK" && data.data && data.data.ticker === code) {
                            const obData = data.data;
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

                stockWs.onclose = (e) => {
                    console.log(`Dashboard WebSocket disconnected. Code: ${e.code}, Reason: ${e.reason}`);
                    stockWs = null;
                };

                stockWs.onerror = (error) => {
                    console.error('Dashboard WebSocket error:', error);
                    stockWs?.close();
                };
            } catch (error) {
                console.error('Failed to initialize WebSocket:', error);
            }
        }, 150);
    },

    // 스트림 정리 함수 (컴포넌트 언마운트 시 호출)
    disconnectStockStream: () => {
        if (stockTimeout) {
            clearTimeout(stockTimeout);
            stockTimeout = null;
        }
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
        }
        console.log('Dashboard WebSocket stream cleaned up');
    }
}));
