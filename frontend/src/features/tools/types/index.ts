export interface ToolItem {
  id: string;
  name: string;
  description: string;
  type: 'BLUE' | 'AMBER' | 'ROSE';
  iconName: string;
}

export interface ToolListResponse {
  tools: ToolItem[];
}

export interface ToolDetailResponse {
  toolId: number;
  projectId: number;
  chatSessionId: number;
  createdByProjectMemberId: number;
  createdByUserId: number;
  createdByUserName: string;
  fileName: string;
  displayName: string;
  displayDescription: string;
  status: 'DRAFT' | 'REVIEW' | 'APPROVED' | 'REJECTED' | 'DELETED';
  draftPhase: 'PLAN' | 'REVIEW';
  draftVersion: number;
  toolGrade?: number;
  rawMarkdown?: string;
  structuredPlanJson?: string;
  draftSnapshot?: string;
  createdAt: string;
  updatedAt: string;
}
