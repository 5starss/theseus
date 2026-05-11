import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';
import { ToolPlanMode } from '@/features/projects/types/chat';
import type {
  ChatMessage,
  ChatSession,
  ChatSessionDetailResponse,
  ToolPlanDetailResponse,
  ToolPlanGenerationRequest,
  ToolPlanGenerationResponse,
  ToolPlanRegenerationRequest,
  ToolPlanRunStateResponse
} from '@/features/projects/types/chat';

export const chatApi = {
  createSession: async (projectId: string) => {
    const response = await apiClient.post<ApiResponse<ChatSession>>(
      `/api/v1/projects/${projectId}/sessions`,
      { title: '새로운 대화 세션' }
    );
    return response.data.result;
  },

  getSessions: async (projectId: string | undefined, page = 0, size = 20) => {
    if (!projectId) return { content: [], totalElements: 0, totalPages: 0, size: 20 };
    const response = await apiClient.get<ApiResponse<PageResponse<ChatSession>>>(
      `/api/v1/projects/${projectId}/sessions`,
      { params: { page, size } }
    );
    return response.data.result;
  },

  getSessionDetails: async (projectId: string, sessionId: string): Promise<ChatSessionDetailResponse> => {
    const response = await apiClient.get<ApiResponse<ChatSessionDetailResponse>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}`
    );
    return response.data.result;
  },

  updateSessionTitle: async (projectId: string, sessionId: string, title: string) => {
    const response = await apiClient.patch<ApiResponse<ChatSession>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}`,
      { title }
    );
    return response.data.result;
  },

  closeSession: async (projectId: string, sessionId: string) => {
    const response = await apiClient.patch<ApiResponse<ChatSession>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/close`
    );
    return response.data.result;
  },

  createMessage: async (projectId: string, sessionId: string, content: string) => {
    const response = await apiClient.post<ApiResponse<ChatMessage>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/messages`,
      { content, messageType: 'CHAT', contentType: 'TEXT' }
    );
    return response.data.result;
  },

  requestToolPlanApproval: async (projectId: string, toolPlanId: string) => {
    const response = await apiClient.post<ApiResponse<unknown>>(
      `/api/v1/projects/${projectId}/tool-plans/${toolPlanId}/approval-requests`
    );
    return response.data.result;
  },

  generateToolPlan: async (
    projectId: string,
    sessionId: string,
    payload: { userMessage: string; mode?: ToolPlanMode }
  ): Promise<ToolPlanGenerationResponse> => {
    const apiPayload: ToolPlanGenerationRequest = {
      mode: payload.mode || ToolPlanMode.PLAN,
      prompt: payload.userMessage
    };
    const response = await apiClient.post<ApiResponse<ToolPlanGenerationResponse>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/tool-plans/generate`,
      apiPayload
    );
    return response.data.result;
  },

  regenerateToolPlan: async (
    projectId: string,
    sessionId: string,
    toolPlanId: string,
    payload: { basePlanVersion: number; feedbackItems: Array<{ blockId: string; comment: string }>; mode?: ToolPlanMode }
  ): Promise<ToolPlanGenerationResponse> => {
    const apiPayload: ToolPlanRegenerationRequest = {
      mode: payload.mode || ToolPlanMode.PLAN,
      basePlanVersion: payload.basePlanVersion,
      feedbackItems: payload.feedbackItems
    };
    const response = await apiClient.patch<ApiResponse<ToolPlanGenerationResponse>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/tool-plans/${toolPlanId}/regenerate`,
      apiPayload
    );
    return response.data.result;
  },

  getToolPlanDetail: async (
    projectId: string,
    sessionId: string,
    toolPlanId: string
  ): Promise<ToolPlanDetailResponse> => {
    const response = await apiClient.get<ApiResponse<ToolPlanDetailResponse>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/tool-plans/${toolPlanId}`
    );
    return response.data.result;
  },

  getToolPlanRunState: async (
    projectId: string,
    sessionId: string,
    runId: string
  ): Promise<ToolPlanRunStateResponse> => {
    const response = await apiClient.get<ApiResponse<ToolPlanRunStateResponse>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/tool-plan-runs/${runId}/state`
    );
    return response.data.result;
  },
};
