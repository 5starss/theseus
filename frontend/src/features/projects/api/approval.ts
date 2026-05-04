import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';
import type { ToolApprovalResponse, ToolApprovalApproveRequest, ToolApprovalRejectRequest } from '@/features/projects/types/approval';

export const approvalApi = {
  /**
   * Tool 승인 요청 목록 조회
   */
  getToolApprovals: async (projectId: string | number, page = 0, size = 20, approvalStatus?: string) => {
    const params: Record<string, string | number> = { page, size };
    if (approvalStatus) {
      params.approvalStatus = approvalStatus;
    }
    const response = await apiClient.get<ApiResponse<PageResponse<ToolApprovalResponse>>>(
      `/api/v1/projects/${projectId}/tool-approvals`,
      { params }
    );
    return response.data.result;
  },

  /**
   * Tool 승인
   */
  approveTool: async (
    projectId: string | number,
    toolApprovalId: number,
    data: ToolApprovalApproveRequest
  ) => {
    const response = await apiClient.patch<ApiResponse<ToolApprovalResponse>>(
      `/api/v1/projects/${projectId}/tool-approvals/${toolApprovalId}/approve`,
      data
    );
    return response.data.result;
  },

  /**
   * Tool 반려
   */
  rejectTool: async (
    projectId: string | number,
    toolApprovalId: number,
    data: ToolApprovalRejectRequest
  ) => {
    const response = await apiClient.patch<ApiResponse<ToolApprovalResponse>>(
      `/api/v1/projects/${projectId}/tool-approvals/${toolApprovalId}/reject`,
      data
    );
    return response.data.result;
  },
};
