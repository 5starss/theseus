import axios from 'axios';
import { useAuthStore } from '@/store/useAuthStore';

// 기본 axios 인스턴스 생성
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080',
  withCredentials: true, // HttpOnly Refresh Token 쿠키를 주고받기 위한 설정
  headers: {
    'Content-Type': 'application/json',
  },
});

// API 요청 시 Access Token을 Authorization 헤더에 첨부하기 위한 요청 인터셉터 추가
apiClient.interceptors.request.use(
  (config) => {
    // 순환 참조(Circular Dependency)를 피하기 위해 getState()를 사용하여 상태를 가져오기
    const token = useAuthStore.getState().accessToken;
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 무한 루프를 방지하기 위해 토큰 갱신용 별도 axios 인스턴스 생성
const refreshClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080',
  withCredentials: true,
});

// 401 Unauthorized, 403 Forbidden 에러 처리를 위한 응답 인터셉터 추가
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    if (
      (error.response?.status === 401 || error.response?.status === 403) &&
      !originalRequest._retry
    ) {
      originalRequest._retry = true;

      try {
        // 쿠키를 포함하여 refresh API 호출
        const refreshResponse = await refreshClient.post('/api/v1/auth/refresh');
        const newAccessToken = refreshResponse.data.result.accessToken;

        // Zustand 스토어에 새 Access Token 저장
        useAuthStore.getState().setAccessToken(newAccessToken);

        // 실패했던 기존 요청의 Authorization 헤더를 새 토큰으로 교체 후 재시도
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh Token마저 만료되었거나 유효하지 않은 경우 로그아웃 처리
        useAuthStore.getState().logout();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
