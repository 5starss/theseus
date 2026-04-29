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

export interface ProjectPageResponse<T> {
  content: T[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
}

export const adminApi = {
  /**
   * 사용자 목록 조회
   */
  getUsers: async () => {
    const response = await apiClient.get<ApiResponse<UserResponse[]>>('/admin/users');
    return response.data.result;
  },

  /**
   * 전체 프로젝트 목록 조회
   */
  getProjects: async (page = 0, size = 20) => {
    const response = await apiClient.get<ApiResponse<ProjectPageResponse<ProjectSummaryResponse>>>(
      '/admin/projects',
      {
        params: { page, size },
      }
    );
    return response.data.result;
  },
};
