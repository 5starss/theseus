export type ToolUsageStatus = 'SUCCESS' | 'FAILED';

export interface ToolUsageRow {
  id: number;
  toolId?: number;
  toolName: string;
  level: number | string | null;
  toolCreatorName: string;
  toolCreatorEmployeeNo: string;
  usedByName: string;
  usedByEmployeeNo: string;
  status: ToolUsageStatus;
  createdAt: string;
  usedAt: string;
  errorMessage?: string | null;
}

export interface ToolUsageListResponse {
  items: ToolUsageRow[];
}
