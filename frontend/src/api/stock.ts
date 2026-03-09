import axios from 'axios';

export interface Stock {
    ticker: string;
    name: string;
    currentPrice: number;
    changeRate: number;
    accVolume: number;
}

export interface ApiResponse<T> {
    isSuccess: boolean;
    code: string;
    message: string;
    result: T;
}

const api = axios.create({
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true,
});

const TOP_40_STOCKS: Record<string, string> = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스",
    "005380": "현대차",
    "000270": "기아",
    "068270": "셀트리온",
    "005490": "POSCO홀딩스",
    "035420": "NAVER",
    "051910": "LG화학",
    "028260": "삼성물산",
    "012330": "현대모비스",
    "105560": "KB금융",
    "055550": "신한지주",
    "032830": "삼성생명",
    "003670": "포스코퓨처엠",
    "035720": "카카오",
    "066570": "LG전자",
    "323410": "카카오뱅크",
    "015760": "한국전력",
    "000810": "삼성화재",
    "316140": "우리금융지주",
    "024110": "기업은행",
    "011200": "HMM",
    "010130": "고려아연",
    "033780": "KT&G",
    "086280": "현대글로비스",
    "017670": "SK텔레콤",
    "009150": "삼성전기",
    "259960": "크래프톤",
    "034020": "두산에너빌리티",
    "036570": "엔씨소프트",
    "018260": "삼성SDS",
    "042700": "한미반도체",
    "010140": "삼성중공업",
    "011170": "롯데케미칼",
    "267250": "HD현대",
    "090430": "아모레퍼시픽",
    "003490": "대한항공",
    "051900": "LG생활건강",
};

const generateDummyStocks = (limit: number): Stock[] => {
    const result: Stock[] = [];
    const entries = Object.entries(TOP_40_STOCKS);

    for (let i = 0; i < limit && i < entries.length; i++) {
        const [ticker, name] = entries[i];

        // 현실적인 더미 데이터 분포
        const currentPrice = Math.floor(Math.random() * 500) * 1000 + 5000;
        const accVolume = Math.floor(Math.random() * 5000000) + 100000;
        const changeRate = parseFloat((Math.random() * 30 - 15).toFixed(2));

        result.push({
            ticker,
            name,
            currentPrice,
            changeRate,
            accVolume
        });
    }

    // 기본값이 VOLUME 정렬(거래량 순)이므로 내림차순 정렬 반환
    return result.sort((a, b) => b.accVolume - a.accVolume);
};

export interface Candle {
    timestamp: string; // "2023-10-01T12:00:00Z"
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export const stockApi = {
    // 백엔드 명세: GET /api/v1/market/stocks?limit=40&rankType=VOLUME
    getTopStocks: async (limit: number = 40, rankType: 'VOLUME' = 'VOLUME'): Promise<Stock[]> => {
        try {
            const response = await api.get<ApiResponse<Stock[]>>(`/api/v1/market/stocks`, {
                params: { limit, rankType }
            });

            if (response.data.isSuccess && response.data.result && response.data.result.length > 0) {
                return response.data.result;
            } else {
                return generateDummyStocks(limit);
            }
        } catch (error) {
            console.warn("Backend is not available for stocks list. Using dummy data.");
            return generateDummyStocks(limit);
        }
    },

    // 백엔드 명세: GET /api/v1/stocks/:ticker/candles
    getCandles: async (ticker: string, interval: string = 'D', limit: number = 50): Promise<Candle[]> => {
        try {
            const response = await api.get<ApiResponse<Candle[]>>(`/api/v1/stocks/${ticker}/candles`, {
                params: { interval, limit }
            });

            if (response.data.isSuccess && response.data.result && response.data.result.length > 0) {
                return response.data.result;
            } else {
                return generateDummyCandles(ticker, interval, limit);
            }
        } catch (error) {
            console.warn(`Backend is not available for candles [${ticker}]. Using dummy data.`);
            return generateDummyCandles(ticker, interval, limit);
        }
    }
};

// Fallback: 가짜 과거 캔들 데이터 생성
const generateDummyCandles = (_ticker: string, interval: string, limit: number): Candle[] => {
    const data: Candle[] = [];
    const now = Math.floor(Date.now() / 1000);

    let candlePeriod = 60; // 1m
    switch (interval) {
        case 'm': candlePeriod = 60; break;
        case 'h': candlePeriod = 3600; break;
        case 'D': candlePeriod = 86400; break;
        case 'W': candlePeriod = 604800; break;
    }

    const alignedNow = Math.floor(now / candlePeriod) * candlePeriod;

    // 원래는 해당 주식의 실제 초기 가격을 가져와야 하나, 목업용으로 50000 시작
    let price = 50000;

    for (let i = limit; i >= 0; i--) {
        const timeStr = new Date((alignedNow - i * candlePeriod) * 1000).toISOString();

        if (i !== limit && i !== 0) {
            price = price + (Math.random() - 0.5) * 500;
            price = Math.round(price / 100) * 100;
        }

        data.push({
            timestamp: timeStr,
            open: price,
            high: price + 200,
            low: price - 200,
            close: price + (Math.random() > 0.5 ? 100 : -100),
            volume: Math.floor(Math.random() * 500000)
        });
    }
    return data;
};
