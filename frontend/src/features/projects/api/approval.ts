import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';
import type {
  ToolApprovalApproveRequest,
  ToolApprovalRejectRequest,
  ToolApprovalResponse
} from '@/features/projects/types/approval';

export const approvalApi = {
  /**
   * ToolPlan 승인 요청 목록을 조회합니다.
   */
  getToolApprovals: async (
    projectId: string | number,
    page = 0,
    size = 20,
    approvalStatus?: string
  ): Promise<PageResponse<ToolApprovalResponse>> => {
    const params: Record<string, string | number> = { page, size };
    if (approvalStatus) {
      params.approvalStatus = approvalStatus;
    }

    try {
      const response = await apiClient.get<ApiResponse<PageResponse<ToolApprovalResponse>>>(
        `/api/v1/projects/${projectId}/tool-approvals`,
        { params }
      );
      return response.data.result;
    } catch (error) {
      console.error('Failed to fetch tool approvals:', error);
      throw error;
    }
  },

  /**
   * ToolPlan 승인 요청을 승인합니다.
   */
  approveTool: async (
    projectId: string | number,
    toolApprovalId: number,
    data: ToolApprovalApproveRequest
  ) => {
    try {
      const response = await apiClient.patch<ApiResponse<ToolApprovalResponse>>(
        `/api/v1/projects/${projectId}/tool-approvals/${toolApprovalId}/approve`,
        data
      );
      return response.data.result;
    } catch (error) {
      console.error(`Failed to approve tool approval ${toolApprovalId}:`, error);
      throw error;
    }
  },

  /**
   * ToolPlan 승인 요청을 반려합니다.
   */
  rejectTool: async (
    projectId: string | number,
    toolApprovalId: number,
    data: ToolApprovalRejectRequest
  ) => {
    try {
      const response = await apiClient.patch<ApiResponse<ToolApprovalResponse>>(
        `/api/v1/projects/${projectId}/tool-approvals/${toolApprovalId}/reject`,
        data
      );
      return response.data.result;
    } catch (error) {
      console.error(`Failed to reject tool approval ${toolApprovalId}:`, error);
      throw error;
    }
  }
};
