import api, { ApiError } from './client';
import type { ApiResponse } from './client';

// 백엔드 명세에 맞춤
export interface SignupRequest {
    email: string;
    password: string;
    nickname: string;
    investmentStyle: "BALANCED" | "GROWTH" | "AGGRESSIVE";
}

export interface SignupResponse {
    userId: number;
}

export interface LoginRequest {
    email: string;
    password: string;
}

export interface LoginResponse {
    tokenType: string;
    accessToken: string;
    nickname: string;
    accessTokenExpiresAt: string;  // 액세스 토큰 만료 시간
}

// 회원가입 엔드포인트
export const authApi = {
    // 회원가입
    signup: async (data: SignupRequest): Promise<SignupResponse> => {
        const response = await api.post<ApiResponse<SignupResponse>>('/api/v1/core/auth/signup', data);

        if (!response.data.isSuccess) {
            throw new ApiError(response.data.code, response.data.message || '회원가입에 실패했습니다.');
        }

        return response.data.result;
    },
    // 로그인
    login: async (data: LoginRequest): Promise<LoginResponse> => {
        const response = await api.post<ApiResponse<LoginResponse>>('/api/v1/core/auth/login', data);

        if (!response.data.isSuccess) {
            throw new ApiError(response.data.code, response.data.message || '로그인에 실패했습니다.');
        }

        return response.data.result;
    },
    // 로그아웃
    logout: async (): Promise<void> => {
        await api.post('/api/v1/core/auth/logout');
    },
};
