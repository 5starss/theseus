import { create } from 'zustand';
import { stockApi } from '../api/stock';
import { watchlistApi } from '../api/watchlist';
import { useSocketStore } from './useSocketStore';
import { useAuthStore } from './useAuthStore';
import { toast } from 'sonner';

// 주식 호가 및 거래 관련 전역 상태 타입
interface StockState {
    stockCode: string;
    stockName: string;

    currentPrice: number;
    priceChange: number;
    changeRate: number;
    lastTickVolume: number; // 마지막 체결 거래량

    askPrice: number;
    askVolume: number;
    bidPrice: number;
    bidVolume: number;

    prevClose: number; // 전일 종가

    selectedOrderPrice: number; // 호가창에서 선택한 가격

    candles: any[]; // 캔들 데이터 배열
    candlesLoading: boolean;

    // 관심 종목 (Watchlist)
    watchlist: Set<string>;
    watchlistLoading: boolean;

    setStock: (code: string) => void;
    setCandles: (candles: any[]) => void;
    appendHistoricalCandles: (historical: any[]) => void;
    setCurrentPrice: (price: number) => void;
    setSelectedOrderPrice: (price: number) => void;
    updateOrderbook: (ask: { price: number; volume: number }, bid: { price: number; volume: number }) => void;
    connectStockStream: (code: string) => void;
    disconnectStockStream: () => void;
    handleWsMessage: (event: CustomEvent) => void;

    // 관심 종목 액션
    fetchWatchlist: () => Promise<void>;
    toggleWatchlist: (ticker: string) => Promise<void>;
}

// Mock database
export const MOCK_STOCKS: Record<string, { name: string; price: number }> = {
    "005930": { name: "삼성전자", price: 188000 },
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

export const useStockStore = create<StockState>((set, get) => ({
    stockCode: '',
    stockName: '',
    currentPrice: 0,
    prevClose: 0,
    priceChange: 0,
    changeRate: 0,
    lastTickVolume: 0,

    askPrice: 0,
    askVolume: 0,
    bidPrice: 0,
    bidVolume: 0,

    selectedOrderPrice: 0,

    candles: [],
    candlesLoading: false,

    watchlist: new Set(),
    watchlistLoading: false,

    // 주식 코드로 초기 데이터 설정
    setStock: (code) =>
        set({
            stockCode: code,
            stockName: '-',
            currentPrice: 0,
            prevClose: 0,
            priceChange: 0,
            changeRate: 0,
            lastTickVolume: 0,
            askPrice: 0,
            askVolume: 0,
            bidPrice: 0,
            bidVolume: 0,
            selectedOrderPrice: 0,
            candles: [],
            candlesLoading: false
        }),

    setSelectedOrderPrice: (price) => set({ selectedOrderPrice: price }),

    setCandles: (candles) => set({ candles }),

    appendHistoricalCandles: (historical) =>
        set((state) => {
            // 시간 순서 보장 및 중복 제거
            const combined = [...historical, ...state.candles];
            const uniqueMap = new Map();
            combined.forEach(c => uniqueMap.set(c.time, c));

            const uniqueSorted = Array.from(uniqueMap.values())
                .sort((a, b) => (a.time as number) - (b.time as number));

            return { candles: uniqueSorted };
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

    // WebSocket 메시지 처리 함수
    handleWsMessage: (event: any) => {
        const rawData = event.detail;
        if (!rawData) return;
        const code = get().stockCode;

        // 백엔드에서 여러 메시지를 \n으로 묶어 보낼 수 있으므로 분리해서 처리
        const lines = rawData.toString().split('\n');

        for (const line of lines) {
            if (!line.trim()) continue;

            try {
                const data = JSON.parse(line);

                if (data.topic === "TICK" && data.data && data.data.ticker === code) {
                    const tickData = data.data;

                    if (!isFinite(tickData.price)) continue;

                    let newPrevClose = get().prevClose;
                    if (newPrevClose === 0 && isFinite(tickData.change_rate) && tickData.change_rate !== -100) {
                        newPrevClose = Math.round(tickData.price / (1 + (tickData.change_rate / 100)));
                    }

                    if (!isFinite(newPrevClose)) newPrevClose = get().prevClose;

                    set({
                        stockName: get().stockName === '-' && tickData.name ? tickData.name : get().stockName,
                        currentPrice: tickData.price,
                        prevClose: newPrevClose,
                        priceChange: isFinite(newPrevClose) && newPrevClose > 0 ? tickData.price - newPrevClose : (tickData.price - get().prevClose || 0),
                        changeRate: isFinite(tickData.change_rate) ? tickData.change_rate : (isFinite(newPrevClose) && newPrevClose > 0 ? ((tickData.price - newPrevClose) / newPrevClose) * 100 : 0),
                        lastTickVolume: tickData.trade_vol || 0
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
            } catch (err) {
                console.error("Failed to parse stock websocket segment", err, line);
            }
        }
    },

    // 주식 스트림 연결
    connectStockStream: (code) => {
        // 즉시 stockCode와 주요 가격 정보를 초기화 (이전 종목 데이터 잔존 방지)
        set({
            stockCode: code,
            currentPrice: 0,
            priceChange: 0,
            changeRate: 0,
            prevClose: 0
        });
        console.log(`Starting Dashboard Stream via Singleton [${code}]...`);

        // 1. 초기 데이터 스냅샷 로딩 (시세 + 호가 병렬 호출)
        Promise.all([
            stockApi.getTickSnapshot(code),
            stockApi.getOrderbook(code)
        ]).then(([tickData, obData]) => {
            const newState: Partial<StockState> = {};

            if (tickData) {
                const cp = tickData.currentPrice;
                const cr = tickData.changeRate;
                const pc = Math.round(cp / (1 + (cr / 100)));

                newState.stockName = tickData.name;
                newState.currentPrice = cp;
                newState.prevClose = pc;
                newState.priceChange = cp - pc;
                newState.changeRate = cr;
            }

            if (obData) {
                newState.askPrice = obData.askPrice1;
                newState.askVolume = obData.askVolume1;
                newState.bidPrice = obData.bidPrice1;
                newState.bidVolume = obData.bidVolume1;
                if (!newState.stockName) newState.stockName = obData.name;
            }

            if (Object.keys(newState).length > 0) {
                set(newState);
            }
        }).catch(err => console.error("Snapshot error", err));

        // 2. 싱글톤 구독
        useSocketStore.getState().subscribe('TICK', code);
        useSocketStore.getState().subscribe('ORDERBOOK', code);

        // 3. 핸들러 등록
        window.addEventListener('ws-message' as any, get().handleWsMessage);
    },

    // 주식 스트림 연결 해제
    disconnectStockStream: () => {
        const code = get().stockCode;
        useSocketStore.getState().unsubscribe('TICK', code);
        useSocketStore.getState().unsubscribe('ORDERBOOK', code);
        window.removeEventListener('ws-message' as any, get().handleWsMessage);
    },

    // 관심종목 목록 조회
    fetchWatchlist: async () => {
        if (!useAuthStore.getState().isLoggedIn) return;
        set({ watchlistLoading: true });
        try {
            const list = await watchlistApi.getWatchlists();
            // 백엔드에서 최신순으로 올 경우, '먼저 추가한 순'으로 보여주기 위해 리스트를 뒤집습니다.
            const orderedTickers = list.map(item => item.ticker).reverse();
            set({ watchlist: new Set(orderedTickers) });
        } catch (error) {
            console.error('Failed to fetch watchlist:', error);
        } finally {
            set({ watchlistLoading: false });
        }
    },

    // 관심종목 토글
    toggleWatchlist: async (ticker) => {
        if (!useAuthStore.getState().isLoggedIn) return;

        const isCurrentlyIn = get().watchlist.has(ticker);
        
        // 갯수 제한: 3개 초과 불가 (추가할 때만 체크)
        if (!isCurrentlyIn && get().watchlist.size >= 3) {
            toast.error('관심종목은 최대 3개까지만 등록 가능합니다.');
            return;
        }

        const newWatchlist = new Set(get().watchlist);

        // Optimistic UI Update
        if (isCurrentlyIn) {
            newWatchlist.delete(ticker);
        } else {
            newWatchlist.add(ticker);
        }
        set({ watchlist: newWatchlist });

        try {
            if (isCurrentlyIn) {
                await watchlistApi.removeWatchlist(ticker);
            } else {
                await watchlistApi.addWatchlist(ticker);
            }
        } catch (error) {
            // Revert on error
            console.error('Failed to toggle watchlist:', error);
            const reverted = new Set(get().watchlist);
            if (isCurrentlyIn) reverted.add(ticker);
            else reverted.delete(ticker);
            set({ watchlist: reverted });
        }
    }
}));
