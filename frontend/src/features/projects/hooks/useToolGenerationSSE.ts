import { useRef, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { toast } from 'sonner';
import { useAuthStore } from '@/store/useAuthStore';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import { chatApi } from '../api/chat';
import type { ToolGenerationSseEvent, ChatMessage, StructuredPlan, DraftPhase } from '../types/chat';

/**
 * Tool 생성/재생성 SSE 스트림을 관리하는 훅.
 * 
 * 사용 흐름:
 *   1. HTTP로 generate/regenerate API 호출 → 응답에서 sseUrl 획득
 *   2. connectSSE(sseUrl) 호출 → SSE 이벤트를 store에 반영
 *   3. completed/failed 시 자동 종료, 또는 disconnectSSE()로 수동 종료
 */
export function useToolGenerationSSE() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const abortRef = useRef<AbortController | null>(null);
  const connectedToolIdRef = useRef<number | null>(null);

  const disconnectSSE = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    connectedToolIdRef.current = null;
  }, []);

  const connectSSE = useCallback((sseUrl: string, toolId?: number) => {
    // 기존 연결 정리 (같은 toolId에 대한 중복 방지)
    if (connectedToolIdRef.current !== null) {
      disconnectSSE();
    }
    if (toolId !== undefined) {
      connectedToolIdRef.current = toolId;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    // sseUrl이 상대 경로면 API baseURL과 조합
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
    const fullUrl = sseUrl.startsWith('http') ? sseUrl : `${baseUrl}${sseUrl}`;

    const token = useAuthStore.getState().accessToken;

    fetchEventSource(fullUrl, {
      method: 'GET',
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        'Accept': 'text/event-stream',
      },
      signal: controller.signal,
      openWhenHidden: true, // 탭 전환 시에도 SSE 유지

      async onmessage(ev) {
        if (!ev.data) return;

        try {
          const data: ToolGenerationSseEvent = JSON.parse(ev.data);
          // ev.event에 이벤트 이름이 있으면 사용, 없으면 data 내부의 eventType 사용
          const eventType = ev.event || data.eventType;

          const store = useChatSessionStore.getState();

          switch (eventType) {
            case 'connected':
              // 연결 성공 — 별도 UI 처리 불필요, 로깅만
              console.log('[SSE] Connected to tool generation stream', data);
              break;

            case 'progress':
              store.setProgressInfo({
                step: data.message || '생성 중...',
                message: data.message || '',
                percent: data.progressRate ?? 0,
              });
              break;

            case 'chunk':
              if (data.content) {
                store.updateLastMessageContent(data.content);
              }
              break;

            case 'completed':
              store.setProgressInfo({
                step: '완료',
                message: data.message || 'Tool PLAN 생성이 완료되었습니다.',
                percent: 100,
              });
              
              // 최신 세션 정보(Plan 등)를 가져와서 스토어 갱신
              if (projectId && sessionId) {
                try {
                  const result = await chatApi.getSessionDetails(projectId, sessionId);
                  const details = result as {
                    messages?: ChatMessage[];
                    currentPlan?: StructuredPlan;
                    draftPhase?: DraftPhase;
                    currentToolId?: string | number;
                    title?: string;
                    isClosed?: boolean;
                  };
                  store.initSession({
                    messages: details.messages || store.messages,
                    plan: details.currentPlan || null,
                    phase: details.draftPhase || 'REVIEW',
                    toolId: details.currentToolId ? String(details.currentToolId) : store.currentToolId,
                    title: details.title || store.title,
                    isClosed: details.isClosed || false
                  });
                } catch (e) {
                  console.error('[SSE] Failed to refresh session details:', e);
                }
              } else {
                // 파라미터가 없는 경우 기본 처리
                store.setDraftPhase('REVIEW');
                if (data.draftVersion !== undefined) {
                  store.setDraftVersion(data.draftVersion);
                }
                if (data.toolId) {
                  store.setCurrentToolId(String(data.toolId));
                }
              }

              store.setIsGenerating(false);
              store.setAbortController(null);
              toast.success('Tool 생성이 완료되었습니다.');
              disconnectSSE();
              break;

            case 'failed':
              store.setIsGenerating(false);
              store.setAbortController(null);
              toast.error(data.errorMessage || 'Tool 생성에 실패했습니다.');
              // 실패 시 시스템 메시지 추가
              store.addMessage({
                messageId: crypto.randomUUID(),
                senderType: 'SYSTEM_NOTICE',
                content: data.errorMessage || 'Tool 생성에 실패했습니다.',
                createdAt: new Date().toISOString(),
              });
              disconnectSSE();
              break;

            default:
              console.warn('[SSE] Unknown event type:', eventType, data);
          }
        } catch {
          console.warn('[SSE] Failed to parse event data:', ev.data);
        }
      },

      onerror(err) {
        console.error('[SSE] Connection error:', err);
        const store = useChatSessionStore.getState();
        store.setIsGenerating(false);
        store.setAbortController(null);
        toast.error('SSE 연결이 끊어졌습니다.');
        disconnectSSE();
        // fetchEventSource가 재연결을 시도하지 않도록 에러를 다시 throw
        throw err;
      },

      onclose() {
        console.log('[SSE] Connection closed');
      },
    });

    // store에 AbortController 저장하여 외부에서도 중단 가능
    useChatSessionStore.getState().setAbortController(controller);
  }, [disconnectSSE, projectId, sessionId]);

  // 컴포넌트 unmount 시 SSE 정리
  useEffect(() => {
    return () => {
      disconnectSSE();
    };
  }, [disconnectSSE]);

  return { connectSSE, disconnectSSE };
}
