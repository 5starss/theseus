import { apiClient } from './client';

export interface LoginRequest {
  loginId: string;
  password?: string; // Optional for admin login simulation if needed, but required by backend
}

export interface LoginResponse {
  tokenType: string;
  accessToken: string;
  userId: number;
  name: string;
  systemRole: 'SUPER_ADMIN' | 'PROJECT_ADMIN' | 'USER'; // Adjust based on actual roles
}

export interface ApiResponse<T> {
  isSuccess: boolean;
  code: string;
  message: string;
  result: T;
}

export const authApi = {
  /**
   * 로그인 API
   * @param data { loginId, password }
   */
  login: async (data: LoginRequest) => {
    // Note: The actual endpoint in backend is /auth/login based on AuthController's @RequestMapping("/auth")
    const response = await apiClient.post<ApiResponse<LoginResponse>>('/auth/login', data);
    return response.data.result;
  },

  /**
   * 로그아웃 API
   */
  logout: async () => {
    const response = await apiClient.post<ApiResponse<void>>('/auth/logout');
    return response.data;
  },
};
