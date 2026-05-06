import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { ProjectMemberResponse } from '@/features/projects/api';
import type { ProjectMemberCreateRequest, ProjectMemberUpdateRequest } from '@/features/projects/types/member';

export const memberApi = {
  /**
   * 프로젝트 멤버 목록 조회
   */
  getMembers: async (projectId: string | number, page = 0, size = 20, status?: string) => {
    const response = await apiClient.get<ApiResponse<ProjectMemberResponse[]>>(
      `/api/v1/projects/${projectId}/members`,
      { params: { page, size, status } }
    );
    return response.data.result;
  },

  /**
   * 프로젝트 멤버 등록
   */
  addMember: async (projectId: string | number, data: ProjectMemberCreateRequest) => {
    const response = await apiClient.post<ApiResponse<ProjectMemberResponse>>(
      `/api/v1/projects/${projectId}/members`,
      data
    );
    return response.data.result;
  },

  /**
   * 프로젝트 멤버 권한 및 상태 수정
   */
  updateMember: async (
    projectId: string | number,
    projectMemberId: number,
    data: ProjectMemberUpdateRequest
  ) => {
    const response = await apiClient.patch<ApiResponse<ProjectMemberResponse>>(
      `/api/v1/projects/${projectId}/members/${projectMemberId}`,
      data
    );
    return response.data.result;
  },
};
