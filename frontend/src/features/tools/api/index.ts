import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';
import type { ToolDetailResponse, ToolItem } from '../types';

export const toolApi = {
  /**
   * 프로젝트의 사용 가능한 Tool 목록을 조회합니다.
   */
  getTools: async (projectId: string | number): Promise<ToolItem[]> => {
    try {
      const response = await apiClient.get<ApiResponse<PageResponse<ToolItem>>>(`/api/v1/projects/${projectId}/tools`);
      return response.data.result?.content || [];
    } catch (error) {
      console.error('Failed to fetch tools:', error);
      throw error;
    }
  },

  /**
   * 실제 생성된 Tool 산출물의 상세 정보를 조회합니다.
   */
  getTool: async (projectId: string | number, toolId: string | number): Promise<ToolDetailResponse | null> => {
    try {
      const response = await apiClient.get<ApiResponse<ToolDetailResponse>>(
        `/api/v1/projects/${projectId}/tools/${toolId}`
      );
      return response.data.result;
    } catch (error) {
      console.error(`Failed to fetch tool ${toolId}:`, error);
      throw error;
    }
  },

  /**
   * Tool 상태를 변경합니다.
   */
  updateToolStatus: async (
    projectId: string | number,
    toolId: string | number,
    status: 'APPROVED' | 'REJECTED'
  ): Promise<boolean> => {
    try {
      await apiClient.patch(`/api/v1/projects/${projectId}/tools/${toolId}/status`, { status });
      return true;
    } catch (error) {
      console.error(`Failed to update tool ${toolId} status:`, error);
      throw error;
    }
  },

  updateToolAccessLevel: async (
    projectId: string | number,
    toolId: string | number,
    accessLevel: number
  ): Promise<ToolItem> => {
    try {
      const response = await apiClient.patch<ApiResponse<ToolItem>>(
        `/api/v1/projects/${projectId}/tools/${toolId}/access-level`,
        { accessLevel }
      );
      return response.data.result;
    } catch (error) {
      console.error(`Failed to update tool ${toolId} access level:`, error);
      throw error;
    }
  },

  /**
   * Tool을 논리 삭제 처리합니다.
   */
  deleteTool: async (projectId: string | number, toolId: string | number): Promise<boolean> => {
    try {
      await apiClient.delete(`/api/v1/projects/${projectId}/tools/${toolId}`);
      return true;
    } catch (error) {
      console.error(`Failed to delete tool ${toolId}:`, error);
      throw error;
    }
  }
};
