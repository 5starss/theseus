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
  toolGrade?: number;
  status: 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'DELETED';
  sourceToolPlanId?: number;
  moduleName?: string;
  artifactPath?: string;
  codeSnapshot?: string;
  metadataJson?: string;
  createdAt: string;
  updatedAt: string;
}
