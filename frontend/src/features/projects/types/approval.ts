export interface ToolApprovalResponse {
  toolApprovalId: number;
  projectId: number;
  toolId: number | null;
  toolPlanId: number | null;
  planGroupId: number | null;
  planVersion: number | null;
  fileName: string | null;
  displayName: string | null;
  requestNumber: number;
  approvalStatus: 'PENDING' | 'APPROVED' | 'REJECTED';
  requestedByProjectMemberId: number;
  requestedByUserId: number;
  requestedByUserName: string;
  reviewedByProjectMemberId: number | null;
  reviewedByUserId: number | null;
  reviewedByUserName: string | null;
  reviewFeedback: string | null;
  requestedAt: string;
  reviewedAt: string | null;
  toolStatus: string | null;
  toolPlanStatus: string | null;
}

export interface ToolApprovalApproveRequest {
  toolGrade: number;
  reviewFeedback?: string;
}

export interface ToolApprovalRejectRequest {
  reviewFeedback: string;
}
