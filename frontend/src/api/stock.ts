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

const generateDummyStocks = (limit: number): Stock[] => {
    const dummyNames = [
        "삼성전자", "SK하이닉스", "LG에너지솔루션", "현대차", "기아", "셀트리온", "POSCO홀딩스", "NAVER", "삼성바이오로직스", "LG화학",
        "삼성SDI", "카카오", "현대모비스", "포스코퓨처엠", "하나금융지주", "LG전자", "카카오뱅크", "신한지주", "SK이노베이션", "메리츠금융지주",
        "삼성물산", "하이브", "에코프로비엠", "두산에너빌리티", "고려아연", "SK텔레콤", "한국전력", "기업은행", "엔씨소프트", "대한항공",
        "한화에어로스페이스", "현대건설", "금호석유", "SK바이오팜", "HD한국조선해양", "아모레퍼시픽", "오리온", "두산밥캣", "LG디스플레이", "현대제철"
    ];

    const result: Stock[] = [];
    for (let i = 0; i < limit; i++) {
        // 실제 삼성전자는 005930이지만 나머지는 순번대로 부가 생성
        const name = dummyNames[i % dummyNames.length];
        const ticker = name === "삼성전자" ? "005930" : String(i + 1).padStart(6, '0');

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

export const stockApi = {
    // 백엔드 명세: GET /api/v1/market/stocks?limit=40&rankType=VOLUME
    getTopStocks: async (limit: number = 40, rankType: 'VOLUME' = 'VOLUME'): Promise<Stock[]> => {
        try {
            const response = await api.get<ApiResponse<Stock[]>>(`/api/v1/market/stocks`, {
                params: { limit, rankType }
            });

            if (response.data.isSuccess && response.data.result) {
                return response.data.result;
            } else {
                // 응답이 정상적이지 않은 경우 더미 반환
                return generateDummyStocks(limit);
            }
        } catch (error) {
            // 백엔드가 꺼져있어 에러가 발생하면 의도된 더미 데이터를 반환
            console.warn("Backend is not available. Using dummy stocks data matching backend format.");
            return generateDummyStocks(limit);
        }
    }
};
