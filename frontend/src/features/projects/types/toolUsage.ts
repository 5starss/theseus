export type ToolUsageStatus = 'SUCCESS' | 'FAILED';

export interface ToolUsageRow {
  id: number;
  toolId?: number | null;
  toolName?: string | null;
  usedByName: string;
  usedByEmployeeNo: string;
  successCount: number;
  failedCount: number;
  status?: ToolUsageStatus | null;
  usedAt?: string | null;
}

export interface ToolUsageListResponse {
  items: ToolUsageRow[];
}
