import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';
import type { ChatSession, ToolGenerationRunResponse } from '@/features/projects/types/chat';

export const chatApi = {
  // 채팅 세션 생성
  createSession: async (projectId: string) => {
    const response = await apiClient.post<ApiResponse<ChatSession>>(
      `/api/v1/projects/${projectId}/sessions`,
      { title: '새로운 대화 세션' }
    );
    return response.data.result;
  },

  // 채팅 세션 목록 조회
  getSessions: async (projectId: string | undefined, page = 0, size = 20) => {
    if (!projectId) return { content: [], totalElements: 0, totalPages: 0, size: 20 };
    const response = await apiClient.get<ApiResponse<PageResponse<ChatSession>>>(
      `/api/v1/projects/${projectId}/sessions`,
      { params: { page, size } }
    );
    return response.data.result;
  },

  // 세션의 기존 채팅 내역 및 상태 조회
  getSessionDetails: async (projectId: string, sessionId: string) => {
    const response = await apiClient.get<ApiResponse<unknown>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}`
    );
    return response.data.result;
  },

  // 채팅 세션 제목 수정
  updateSessionTitle: async (projectId: string, sessionId: string, title: string) => {
    const response = await apiClient.patch<ApiResponse<ChatSession>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}`,
      { title }
    );
    return response.data.result;
  },

  // 채팅 세션 종료
  closeSession: async (projectId: string, sessionId: string) => {
    const response = await apiClient.patch<ApiResponse<ChatSession>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/close`
    );
    return response.data.result;
  },

  // Tool 생성 승인 요청
  requestToolApproval: async (projectId: string, toolId: string) => {
    const response = await apiClient.post<ApiResponse<unknown>>(
      `/api/v1/projects/${projectId}/tools/${toolId}/approval-requests`
    );
    return response.data.result;
  },

  // Tool 생성 (HTTP POST) — 응답의 sseUrl로 별도 SSE 구독 필요
  generateTool: async (
    projectId: string,
    sessionId: string,
    payload: { userMessage: string; fileName: string }
  ): Promise<ToolGenerationRunResponse> => {
    const apiPayload = {
      mode: 'PLAN',
      prompt: payload.userMessage
    };
    const response = await apiClient.post<ApiResponse<ToolGenerationRunResponse>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/tool-plans/generate`,
      apiPayload
    );
    return response.data.result;
  },

  // Tool 재생성 (HTTP PATCH) — 응답의 sseUrl로 별도 SSE 구독 필요
  regenerateTool: async (
    projectId: string,
    sessionId: string,
    toolId: string,
    payload: { baseDraftVersion: number; feedbackItems: Array<{ blockId: string; comment: string }> }
  ): Promise<ToolGenerationRunResponse> => {
    const response = await apiClient.patch<ApiResponse<ToolGenerationRunResponse>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/tools/${toolId}/regenerate`,
      payload
    );
    return response.data.result;
  },

  // Tool 생성/재생성 상태 조회 (HTTP GET)
  getToolGenerationState: async (
    projectId: string,
    sessionId: string,
    toolId: string
  ) => {
    const response = await apiClient.get<ApiResponse<import('@/features/projects/types/chat').ToolGenerationStateResponse>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}/tools/${toolId}/generation-state`
    );
    return response.data.result;
  },
};
