import client from './client';
import type { ApiResponse } from './client';

export interface RankingDto {
    userId: number;
    rank: number;
    nickname: string;
    roi: number;
    rankDate: string;
    percentile: number;
}

export interface PageResponse<T> {
    content: T[];
    page: number;
    size: number;
    totalElements: number;
    totalPages: number;
    last: boolean;
}

export interface RankingSnapshotResponse {
    myRanking: RankingDto | null;
    rankings: PageResponse<RankingDto>;
}

export const rankingApi = {
    /**
     * 전체 랭킹 및 내 랭킹 정보 조회
     */
    getRankings: (page = 0, size = 10, nickname?: string) => {
        return client.get<ApiResponse<RankingSnapshotResponse>>('/api/v1/core/rankings', {
            params: { page, size, nickname }
        });
    },

    /**
     * (관리자/테스트용) 수동 랭킹 스냅샷 생성
     */
    createSnapshot: () => {
        return client.post<ApiResponse<void>>('/api/v1/core/rankings/snapshot');
    }
};
