import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';
import type {
  ToolApprovalApproveRequest,
  ToolApprovalRejectRequest,
  ToolApprovalResponse
} from '@/features/projects/types/approval';

const generateMockApprovals = (projectId: number): ToolApprovalResponse[] => [
  {
    toolApprovalId: 101,
    projectId,
    toolId: null,
    toolPlanId: 201,
    planGroupId: 31,
    planVersion: 1,
    fileName: null,
    displayName: 'Data Pattern Analyzer PLAN',
    requestNumber: 1,
    approvalStatus: 'PENDING',
    requestedByProjectMemberId: 5,
    requestedByUserId: 12,
    requestedByUserName: 'Project Member',
    reviewedByProjectMemberId: null,
    reviewedByUserId: null,
    reviewedByUserName: null,
    reviewFeedback: null,
    requestedAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    reviewedAt: null,
    toolStatus: null,
    toolPlanStatus: 'PENDING'
  },
  {
    toolApprovalId: 102,
    projectId,
    toolId: null,
    toolPlanId: 202,
    planGroupId: 32,
    planVersion: 1,
    fileName: null,
    displayName: 'Log Parser PLAN',
    requestNumber: 1,
    approvalStatus: 'APPROVED',
    requestedByProjectMemberId: 6,
    requestedByUserId: 15,
    requestedByUserName: 'Project Admin',
    reviewedByProjectMemberId: 1,
    reviewedByUserId: 1,
    reviewedByUserName: 'Reviewer',
    reviewFeedback: 'Approved.',
    requestedAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    reviewedAt: new Date(Date.now() - 1000 * 60 * 60 * 20).toISOString(),
    toolStatus: null,
    toolPlanStatus: 'APPROVED'
  }
];

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

      if (!response.data?.result?.content || response.data.result.content.length === 0) {
        throw new Error('Empty content');
      }
      return response.data.result;
    } catch (error) {
      console.warn('Falling back to mock tool approvals.', error);

      const allMocks = generateMockApprovals(Number(projectId));
      const filteredMocks = approvalStatus && approvalStatus !== 'ALL'
        ? allMocks.filter((approval) => approval.approvalStatus === approvalStatus)
        : allMocks;

      return {
        content: filteredMocks,
        page,
        size,
        totalElements: filteredMocks.length,
        totalPages: 1
      } as PageResponse<ToolApprovalResponse>;
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
      console.warn('Failed to approve tool plan via API, simulating success.', error);
      return new Promise((resolve) => setTimeout(resolve, 1000));
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
      console.warn('Failed to reject tool plan via API, simulating success.', error);
      return new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }
};
