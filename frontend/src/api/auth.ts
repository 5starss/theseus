import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';

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
    accessTokenExpiresAt: string;  // 액세스 토큰 만료 시간
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
    withCredentials: true, // 쿠키 전송을 위해 필요
});

// Request Interceptor: 모든 API 요청에 accessToken을 담아서 보냄
api.interceptors.request.use(
    (config) => {
        const token = useAuthStore.getState().token;
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response Interceptor: 401 응답 시 리프레시 토큰으로 자동 갱신
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // 401 Unauthorized 에러이고, 재시도한 적이 없는 요청이며, 
        // 갱신 요청 자체(/api/v1/auth/refresh)나 로그인 요청에서 난 에러가 아닌 경우
        if (
            error.response?.status === 401 &&
            !originalRequest._retry &&
            originalRequest.url !== '/api/v1/auth/refresh' &&
            originalRequest.url !== '/api/v1/auth/login'
        ) {
            originalRequest._retry = true;

            try {
                // 리프레시 토큰(쿠키)을 통해 새로운 액세스 토큰 발급 요청
                const refreshResponse = await axios.post<ApiResponse<{ accessToken: string }>>(
                    '/api/v1/auth/refresh',
                    {},
                    { withCredentials: true }
                );

                if (refreshResponse.data.isSuccess) {
                    const newAccessToken = refreshResponse.data.result.accessToken;
                    const email = useAuthStore.getState().user?.email || '';

                    // 스토어 업데이트
                    useAuthStore.getState().login(email, newAccessToken);

                    // 원래 요청의 헤더를 새 토큰으로 교체하고 재요청
                    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
                    return api(originalRequest);
                }
            } catch (refreshError) {
                // 리프레시 토큰마저 만료/유효하지 않은 경우 -> 로그아웃 처리
                useAuthStore.getState().logout();

                // 홈으로 리다이렉트
                window.location.href = '/';
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);

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
    // 로그인
    login: async (data: LoginRequest): Promise<LoginResponse> => {
        const response = await api.post<ApiResponse<LoginResponse>>('/api/v1/auth/login', data);

        if (!response.data.isSuccess) {
            throw new Error(response.data.message || '로그인에 실패했습니다.');
        }

        return response.data.result;
    },
    // 로그아웃
    logout: async (): Promise<void> => {
        await api.post('/api/v1/auth/logout');
    },
};
