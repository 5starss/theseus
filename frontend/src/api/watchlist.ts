import api from './client';
import type { ApiResponse } from './client';

export interface WatchlistResponse {
    ticker: string;
    companyName: string;
    marketType: string;
    logoUrl: string | null;
    isHeld: boolean;
    quantity: number;
}

const BASE_URL = '/api/v1/core/watchlists';

export const watchlistApi = {
    /**
     * 관심 종목 목록 조회
     */
    getWatchlists: async (): Promise<WatchlistResponse[]> => {
        const response = await api.get<ApiResponse<WatchlistResponse[]>>(BASE_URL);

        if (response.data.isSuccess && response.data.result) {
            return response.data.result;
        }
        return [];
    },

    /**
     * 관심 종목 등록
     * @param ticker 종목 코드
     */
    addWatchlist: async (ticker: string): Promise<void> => {
        await api.post<ApiResponse<void>>(BASE_URL, { ticker });
    },

    /**
     * 관심 종목 삭제
     * @param ticker 종목 코드
     */
    removeWatchlist: async (ticker: string): Promise<void> => {
        await api.delete<ApiResponse<void>>(`${BASE_URL}/${ticker}`);
    }
};
