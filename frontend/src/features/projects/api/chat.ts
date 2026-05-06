import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { PageResponse } from '@/features/admin/api';
import type { ChatSession } from '@/features/projects/types/chat';
import { fetchEventSource } from '@microsoft/fetch-event-source';

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

  // SSE를 통한 Tool 생성 (Generate / Regenerate)
  generateToolStream: (
    projectId: string,
    sessionId: string,
    toolId: string | null,
    payload: Record<string, unknown>,
    onMessage: (event: unknown) => void,
    onError: (err: unknown) => void,
    onClose: () => void
  ) => {
    const url = toolId
      ? `/api/v1/projects/${projectId}/sessions/${sessionId}/tools/${toolId}/regenerate` // PATCH for regenerate? Wait, fetchEventSource supports custom methods.
      : `/api/v1/projects/${projectId}/sessions/${sessionId}/tools/generate`;

    const method = toolId ? 'PATCH' : 'POST';

    // 토큰 가져오기 (localStorage 등에서)
    const authStorage = localStorage.getItem('auth-storage');
    let token = '';
    if (authStorage) {
      try {
        const parsed = JSON.parse(authStorage);
        token = parsed.state?.accessToken || '';
      } catch (e) {
        console.error('Failed to parse auth token', e);
      }
    }

    const abortController = new AbortController();

    fetchEventSource(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal: abortController.signal,
      onmessage(ev) {
        onMessage(ev);
      },
      onerror(err) {
        onError(err);
        throw err; // To stop retrying
      },
      onclose() {
        onClose();
      }
    });

    return abortController;
  }
};
