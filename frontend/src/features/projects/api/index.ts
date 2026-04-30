import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';

export interface MyProjectResponse {
  projectId: number;
  name: string;
  description: string;
  projectStatus: 'ACTIVE' | 'INACTIVE';
  projectRole: 'ADMIN' | 'MEMBER';
  memberStatus: 'ACTIVE' | 'INACTIVE';
  projectAdminUserId: number;
  projectAdminEmployeeNumber: string;
  projectAdminName: string;
  isProjectAdminUser: boolean;
  createdAt: string;
  updatedAt: string;
}

export const projectApi = {
  /**
   * 내 프로젝트 목록 조회
   */
  getMyProjects: async (page = 0, size = 20) => {
    const response = await apiClient.get<ApiResponse<PageResponse<MyProjectResponse>>>('/api/v1/projects', {
      params: { page, size },
    });
    return response.data.result;
  },
};
