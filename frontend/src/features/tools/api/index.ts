import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { ToolDetailResponse, ToolItem } from '../types';

export const mockTools: ToolItem[] = [
  {
    id: 'tool-1',
    name: 'API Error Helper',
    description: 'Analyzes endpoint responses and suggests fixes.',
    type: 'BLUE',
    iconName: 'TerminalSquare'
  },
  {
    id: 'tool-2',
    name: 'Data Pattern Analyzer',
    description: 'Finds hidden correlations and anomalies in datasets.',
    type: 'AMBER',
    iconName: 'LineChart'
  },
  {
    id: 'tool-3',
    name: 'System Optimizer',
    description: 'Detects resource issues and suggests allocation changes.',
    type: 'BLUE',
    iconName: 'Cpu'
  }
];

export const toolApi = {
  /**
   * 프로젝트의 사용 가능한 Tool 목록을 조회합니다.
   */
  getTools: async (projectId: string | number): Promise<ToolItem[]> => {
    try {
      const response = await apiClient.get<ApiResponse<ToolItem[]>>(`/api/v1/projects/${projectId}/tools`);

      if (!Array.isArray(response.data?.result) || response.data.result.length === 0) {
        console.warn('API returned empty or non-array tools, using mock data.');
        return mockTools;
      }

      return response.data.result;
    } catch (error) {
      console.warn('Failed to fetch tools from API, falling back to mock data.', error);
      return mockTools;
    }
  },

  /**
   * 실제 생성된 Tool 산출물의 상세 정보를 조회합니다.
   */
  getTool: async (projectId: string | number, toolId: string | number): Promise<ToolDetailResponse | null> => {
    try {
      const response = await apiClient.get<ApiResponse<ToolDetailResponse>>(
        `/api/v1/projects/${projectId}/tools/${toolId}`
      );
      return response.data.result;
    } catch (error) {
      console.warn(`Failed to fetch tool ${toolId} from API, falling back to mock data.`, error);

      const idStr = String(toolId);
      const parsedToolId = typeof toolId === 'number' ? toolId : parseInt(idStr.replace(/\D/g, '') || '0', 10);
      const codeSnapshot = `def execute(params):
    source = params.get("source", "default")
    return f"Analyzed {source}"
`;

      return {
        toolId: parsedToolId,
        projectId: Number(projectId),
        chatSessionId: 1,
        createdByProjectMemberId: 1,
        createdByUserId: 1,
        createdByUserName: 'Mock User',
        fileName: 'data_analyzer.py',
        displayName: 'Data Analyzer',
        displayDescription: 'Analyzes data patterns.',
        status: 'APPROVED',
        toolGrade: 1,
        sourceToolPlanId: 1,
        moduleName: 'data_analyzer',
        artifactPath: 'projects/mock/data_analyzer.py',
        codeSnapshot,
        metadataJson: JSON.stringify({ language: 'python' }),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
    }
  },

  /**
   * Tool 상태를 변경합니다.
   */
  updateToolStatus: async (
    projectId: string | number,
    toolId: string | number,
    status: 'APPROVED' | 'REJECTED'
  ): Promise<boolean> => {
    try {
      await apiClient.patch(`/api/v1/projects/${projectId}/tools/${toolId}/status`, { status });
      return true;
    } catch (error) {
      console.warn(`Failed to update tool ${toolId} status to ${status}, falling back to mock delay.`, error);
      return new Promise((resolve) => setTimeout(() => resolve(true), 1000));
    }
  }
};
