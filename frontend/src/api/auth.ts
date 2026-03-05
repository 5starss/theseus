import axios from 'axios';

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
    // 로컬 개발 시 vite proxy를 사용하므로, 반드시 하드코딩된 호스트를 사용할 필요 없음. 상대 경로만 사용하면 됨.
});

// 회원가입 엔드포인트
export const authApi = {
    // 회원가입
    signup: async (data: SignupRequest): Promise<SignupResponse> => {
        const response = await api.post<ApiResponse<SignupResponse>>('/api/v1/auth/signup', data);

        if (!response.data.isSuccess) {
            throw new Error(response.data.message || '회원가입에 실패했습니다.');
        }

        return response.data.result;
    },
};
