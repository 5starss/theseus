import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export const chatApi = {
  // 채팅 세션 생성
  createSession: async (projectId: string) => {
    const response = await apiClient.post<ApiResponse<any>>(
      `/api/v1/projects/${projectId}/sessions`,
      { title: '새로운 대화 세션' }
    );
    return response.data.result;
  },

  // 세션의 기존 채팅 내역 및 상태 조회 (가정)
  getSessionDetails: async (projectId: string, sessionId: string) => {
    const response = await apiClient.get<ApiResponse<any>>(
      `/api/v1/projects/${projectId}/sessions/${sessionId}`
    );
    return response.data.result;
  },

  // Tool 생성 승인 요청
  requestToolApproval: async (projectId: string, toolId: string) => {
    const response = await apiClient.post<ApiResponse<any>>(
      `/api/v1/projects/${projectId}/tools/${toolId}/approval-requests`
    );
    return response.data.result;
  },

  // SSE를 통한 Tool 생성 (Generate / Regenerate)
  generateToolStream: (
    projectId: string,
    sessionId: string,
    toolId: string | null,
    payload: any,
    onMessage: (event: any) => void,
    onError: (err: any) => void,
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
