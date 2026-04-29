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

// 401 Unauthorized 에러 처리를 위한 응답 인터셉터 추가 (토큰 갱신 로직이 들어갈 자리)
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    // 추후 필요 시 이곳에 토큰 갱신 로직을 구현
    // const originalRequest = error.config;
    // if (error.response?.status === 401 && !originalRequest._retry) { ... }

    return Promise.reject(error);
  }
);
