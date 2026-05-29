import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { ToolUsageListResponse } from '@/features/projects/types/toolUsage';

export const toolUsageApi = {
  getToolUsages: async (projectId: string | number): Promise<ToolUsageListResponse> => {
    const response = await apiClient.get<ApiResponse<ToolUsageListResponse>>(
      `/api/v1/projects/${projectId}/admin/tool-usages`
    );
    return response.data.result;
  },
};
