import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';

// 공통 API 인터페이스
export interface ApiResponse<T> {
    isSuccess: boolean;
    code: string;
    message: string;
    result: T;
}

/**
 * 백엔드 커스텀 에러 정보를 처리하기 위한 클래스
 */
export class ApiError extends Error {
    code: string;

    constructor(code: string, message: string) {
        super(message);
        this.code = code;
        this.name = 'ApiError';
        // Ensure instanceof works
        Object.setPrototypeOf(this, ApiError.prototype);
    }
}

const client = axios.create({
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true,
});

// Request Interceptor: 모든 API 요청에 accessToken을 담아서 보냄
client.interceptors.request.use(
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
client.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // 401 Unauthorized 에러이고, 재시도한 적이 없는 요청이며, 
        // 갱신 요청 자체나 로그인 요청에서 난 에러가 아닌 경우
        if (
            error.response?.status === 401 &&
            !originalRequest._retry &&
            !originalRequest.url?.includes('/auth/refresh') &&
            !originalRequest.url?.includes('/auth/login')
        ) {
            originalRequest._retry = true;

            try {
                // 리프레시 토큰(쿠키)을 통해 새로운 액세스 토큰 발급 요청
                const refreshResponse = await axios.post<ApiResponse<{ userId: number, accessToken: string, nickname: string }>>(
                    '/api/v1/core/auth/refresh',
                    {},
                    { withCredentials: true }
                );

                if (refreshResponse.data.isSuccess) {
                    const { userId: newUserId, accessToken: newAccessToken, nickname: newNickname } = refreshResponse.data.result;
                    const user = useAuthStore.getState().user;
                    const email = user?.email || '';

                    // 스토어 업데이트 (신규 토큰 및 최신 닉네임 반영)
                    useAuthStore.getState().login(newUserId, email, newAccessToken, newNickname);

                    // 원래 요청의 헤더를 새 토큰으로 교체하고 재요청
                    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
                    return client(originalRequest);
                }
            } catch (refreshError) {
                // 리프레시 토큰마저 만료/유효하지 않은 경우 -> 로그아웃 처리 및 리다이렉트 (사용자 세션이 있었을 때만)
                const user = useAuthStore.getState().user;
                useAuthStore.getState().logout();

                if (user) {
                    window.location.href = '/';
                }
                return Promise.reject(refreshError);
            }
        }

        // 백엔드에서 에러 코드와 메시지를 명시적으로 돌려준 경우 (400, 409 등 non-2xx)
        if (error.response?.data && typeof error.response.data === 'object' && 'code' in error.response.data) {
            const { code, message } = error.response.data;
            return Promise.reject(new ApiError(code, message));
        }

        return Promise.reject(error);
    }
);

export default client;
