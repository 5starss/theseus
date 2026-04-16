import api from './client';
import type { ApiResponse } from './client';

export type InvestmentStyle = "BALANCED" | "GROWTH" | "AGGRESSIVE";

export interface UserProfile {
    userId: number;
    email: string;
    nickname: string;
    investmentStyle: InvestmentStyle;
}

export interface InvestmentStyleUpdateRequest {
    investmentStyle: InvestmentStyle;
}

export const userApi = {
    // 내 정보 조회
    getUserProfile: async (): Promise<UserProfile> => {
        const response = await api.get<ApiResponse<UserProfile>>('/api/v1/core/users/me');
        if (!response.data.isSuccess) {
            throw new Error(response.data.message || '프로필 정보를 가져오는데 실패했습니다.');
        }
        return response.data.result;
    },

    // 투자 성향 변경
    updateInvestmentStyle: async (style: InvestmentStyle): Promise<UserProfile> => {
        const response = await api.patch<ApiResponse<UserProfile>>('/api/v1/core/users/me/investment-style', {
            investmentStyle: style
        });
        if (!response.data.isSuccess) {
            throw new Error(response.data.message || '투자 성향 수정에 실패했습니다.');
        }
        return response.data.result;
    }
};
