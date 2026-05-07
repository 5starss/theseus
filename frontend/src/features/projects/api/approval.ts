import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';
import type { ToolApprovalResponse, ToolApprovalApproveRequest, ToolApprovalRejectRequest } from '@/features/projects/types/approval';

const generateMockApprovals = (projectId: number): ToolApprovalResponse[] => [
  {
    toolApprovalId: 101,
    projectId,
    toolId: 2, // 짝수: REVIEW 시뮬레이션
    fileName: 'complex_data_analyzer.py',
    displayName: '데이터 패턴 분석기',
    requestNumber: 1,
    approvalStatus: 'PENDING',
    requestedByProjectMemberId: 5,
    requestedByUserId: 12,
    requestedByUserName: '김개발 (Backend)',
    reviewedByProjectMemberId: null,
    reviewedByUserId: null,
    reviewedByUserName: null,
    reviewFeedback: null,
    requestedAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2시간 전
    reviewedAt: null,
    toolStatus: 'REVIEW',
    draftPhase: 'CODE_GENERATION'
  },
  {
    toolApprovalId: 102,
    projectId,
    toolId: 4,
    fileName: 'log_parser.py',
    displayName: '로그 분석 엔진',
    requestNumber: 1,
    approvalStatus: 'APPROVED',
    requestedByProjectMemberId: 6,
    requestedByUserId: 15,
    requestedByUserName: '이프론트 (Frontend)',
    reviewedByProjectMemberId: 1,
    reviewedByUserId: 1,
    reviewedByUserName: '박관리 (Admin)',
    reviewFeedback: '코드 컨벤션 훌륭합니다. 승인합니다.',
    requestedAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1일 전
    reviewedAt: new Date(Date.now() - 1000 * 60 * 60 * 20).toISOString(),
    toolStatus: 'APPROVED',
    draftPhase: 'COMPLETED'
  },
  {
    toolApprovalId: 103,
    projectId,
    toolId: 6,
    fileName: 'insecure_script.py',
    displayName: '임시 스크립트',
    requestNumber: 2,
    approvalStatus: 'REJECTED',
    requestedByProjectMemberId: 5,
    requestedByUserId: 12,
    requestedByUserName: '김개발 (Backend)',
    reviewedByProjectMemberId: 1,
    reviewedByUserId: 1,
    reviewedByUserName: '박관리 (Admin)',
    reviewFeedback: '보안 취약점이 존재합니다. eval() 사용을 지양해주세요.',
    requestedAt: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(), // 2일 전
    reviewedAt: new Date(Date.now() - 1000 * 60 * 60 * 40).toISOString(),
    toolStatus: 'DRAFT',
    draftPhase: 'TESTING'
  }
];

export const approvalApi = {
  /**
   * Tool 승인 요청 목록 조회
   */
  getToolApprovals: async (projectId: string | number, page = 0, size = 20, approvalStatus?: string): Promise<PageResponse<ToolApprovalResponse>> => {
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
        console.warn('API returned empty tool approvals, using mock data.');
        throw new Error('Empty content');
      }
      return response.data.result;
    } catch (error) {
      console.warn('Falling back to mock tool approvals.', error);

      const allMocks = generateMockApprovals(Number(projectId));
      const filteredMocks = approvalStatus && approvalStatus !== 'ALL' 
        ? allMocks.filter(m => m.approvalStatus === approvalStatus)
        : allMocks;

      return {
        content: filteredMocks,
        page: page,
        size: size,
        totalElements: filteredMocks.length,
        totalPages: 1,
      } as PageResponse<ToolApprovalResponse>;
    }
  },
  /**
   * Tool 승인
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
      console.warn('Failed to approve tool via API, simulating success.', error);
      return new Promise((resolve) => setTimeout(resolve, 1000));
    }
  },

  /**
   * Tool 반려
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
      console.warn('Failed to reject tool via API, simulating success.', error);
      return new Promise((resolve) => setTimeout(resolve, 1000));
    }
  },
};
