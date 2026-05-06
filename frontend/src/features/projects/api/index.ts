import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse, ProjectResponse } from '@/features/admin/api';

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

export interface ProjectMemberResponse {
  projectMemberId: number;
  projectId: number;
  projectName: string;
  userId: number;
  employeeNumber: string;
  name: string;
  projectRole: 'ADMIN' | 'MANAGER' | 'MEMBER';
  accessLevel: number;
  canCreateTool: boolean;
  canUseTool: boolean;
  canUpdateTool: boolean;
  canDeleteTool: boolean;
  status: 'IN_PROGRESS' | 'COMPLETED';
  isProjectAdminUser: boolean;
  createdByUserId: number | null;
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

  /**
   * 내 프로젝트 권한 조회
   */
  getProjectMe: async (projectId: string | number) => {
    const response = await apiClient.get<ApiResponse<ProjectMemberResponse>>(`/api/v1/projects/${projectId}/me`);
    // 백엔드 응답 구조에 맞춰 result 또는 data 자체를 반환
    return response.data.result || (response.data as unknown as ProjectMemberResponse);
  },

  /**
   * 프로젝트 상세 조회
   */
  getProject: async (projectId: string | number) => {
    const response = await apiClient.get<ApiResponse<ProjectResponse>>(`/api/v1/projects/${projectId}`);
    return response.data.result;
  },

  /**
   * 프로젝트 정보 수정
   */
  updateProject: async (projectId: string | number, data: { name: string; description: string; status: 'ACTIVE' | 'INACTIVE' }) => {
    // data: ProjectUpdateRequest (name, description, status)
    const response = await apiClient.patch<ApiResponse<unknown>>(`/api/v1/projects/${projectId}`, data);
    return response.data.result;
  },
};
