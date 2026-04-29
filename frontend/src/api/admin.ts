import { apiClient } from './client';
import type { ApiResponse } from './auth';

export interface UserResponse {
  id: number;
  employeeNumber: string;
  name: string;
  email: string;
  systemRole: 'SUPER_ADMIN' | 'USER';
  status: 'ACTIVE' | 'INACTIVE';
  createdAt: string;
  updatedAt: string;
}

export interface ProjectSummaryResponse {
  projectId: number;
  name: string;
  description: string;
  status: 'ACTIVE' | 'INACTIVE';
  projectAdminUserId: number;
  projectAdminEmployeeNumber: string;
  projectAdminName: string;
  createdAt: string;
  updatedAt: string;
}

export interface PageResponse<T> {
  content: T[];
  number?: number;
  page?: number;
  size: number;
  totalElements: number;
  totalPages: number;
}

export interface UserCreateRequest {
  employeeNumber: string;
  name: string;
  email: string;
  password?: string;
  systemRole?: 'SUPER_ADMIN' | 'USER';
  status?: 'ACTIVE' | 'INACTIVE';
}

export const adminApi = {
  /**
   * 사용자 목록 조회
   */
  getUsers: async (page = 0, size = 10) => {
    const response = await apiClient.get<ApiResponse<PageResponse<UserResponse>>>('/api/v1/admin/users', {
      params: { page, size }
    });
    return response.data.result;
  },

  /**
   * 사용자 계정 발급
   */
  createUser: async (data: UserCreateRequest) => {
    const response = await apiClient.post<ApiResponse<UserResponse>>('/api/v1/admin/users', data);
    return response.data.result;
  },

  /**
   * 전체 프로젝트 목록 조회
   */
  getProjects: async (page = 0, size = 8) => {
    const response = await apiClient.get<ApiResponse<PageResponse<ProjectSummaryResponse>>>(
      '/api/v1/admin/projects',
      {
        params: { page, size },
      }
    );
    return response.data.result;
  },
};
