export interface ToolApprovalResponse {
  toolApprovalId: number;
  projectId: number;
  toolId: number;
  fileName: string;
  displayName: string;
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
  toolStatus: string;
  draftPhase: string;
}

export interface ToolApprovalApproveRequest {
  toolGrade: number;
  reviewFeedback?: string;
}

export interface ToolApprovalRejectRequest {
  reviewFeedback: string;
}
