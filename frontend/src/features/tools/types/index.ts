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
  fileName: string;
  version: number;
  pythonCode: string;
  status: 'DRAFT' | 'REVIEW' | 'APPROVED' | 'REJECTED';
  createdAt: string;
  updatedAt: string;
  createdByProjectMemberId: number;
}
