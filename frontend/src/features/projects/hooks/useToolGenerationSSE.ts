import { useRef, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { toast } from 'sonner';
import { useAuthStore } from '@/store/useAuthStore';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import { chatApi } from '../api/chat';
import type { ToolGenerationSseEvent, DraftPhase } from '../types/chat';

/**
 * Tool 생성/재생성 SSE 스트림을 관리하는 훅.
 * 
 * 사용 흐름:
 *   1. HTTP로 generate/regenerate API 호출 → 응답에서 sseUrl 획득
 *   2. connectSSE(sseUrl, 'PLAN' 또는 'BUILD') 호출 → SSE 이벤트를 store에 반영
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

  const connectSSE = useCallback((sseUrl: string, flow: 'PLAN' | 'BUILD', id?: string | number) => {
    // 기존 연결 정리
    if (connectedToolIdRef.current !== null) {
      disconnectSSE();
    }
    if (id !== undefined && typeof id === 'number') {
      connectedToolIdRef.current = id;
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

          // 이벤트 타입 정규화: 백엔드가 소문자(progress, completed, failed)로 보내는 경우 대응
          const rawEventType = ev.event || data.eventType;
          const normalized = rawEventType.toUpperCase();
          // 백엔드 이벤트명 → 프론트 이벤트명 매핑
          const eventType = normalized === 'COMPLETED' ? 'TOOL_PLAN_COMPLETED'
                          : normalized === 'FAILED' ? 'ERROR'
                          : normalized;

          const store = useChatSessionStore.getState();

          switch (eventType) {
            case 'CONNECTED':
              console.log('[SSE] Connected to tool generation stream', data);
              break;

            case 'PROGRESS':
              store.setProgressInfo({
                step: data.message || '생성 중...',
                message: data.message || '',
                percent: data.progressRate ?? 0,
              });
              break;

            case 'CHUNK':
              if (data.content) {
                store.updateLastMessageContent(data.content);
              }
              break;

            case 'TOOL_PLAN_COMPLETED':
              if (flow === 'BUILD') break;
              
              store.setProgressInfo({
                step: '완료',
                message: data.message || 'Tool PLAN 생성이 완료되었습니다.',
                percent: 100,
              });

              // 최신 세션 정보(Plan 등)를 가져와서 스토어 갱신
              if (projectId && sessionId) {
                try {
                  const details = await chatApi.getSessionDetails(projectId, sessionId);

                  const toolId = details.createdTool ? String(details.createdTool.toolId) : null;
                  let toolPlanId = details.currentPlan ? String(details.currentPlan.toolPlanId) : store.currentToolPlanId;
                  if (!toolPlanId && data.toolPlanId) {
                    toolPlanId = String(data.toolPlanId);
                  }

                  let phase: DraftPhase = 'REVIEW';
                  if (details.currentPlan?.status === 'REVIEW') phase = 'REVIEW';
                  else if (details.createdTool) phase = 'APPROVED';

                  store.initSession({
                    messages: details.messages || [],
                    plan: store.currentPlan,
                    phase: phase,
                    toolId: toolId,
                    toolPlanId: toolPlanId,
                    toolResult: null,
                    title: details.title || store.title,
                    isClosed: details.isClosed || false,
                    planVersion: data.planVersion || details.currentPlan?.planVersion || store.planVersion,
                    draftVersion: store.draftVersion,
                  });
                } catch (e) {
                  console.error('[SSE] Failed to refresh session details for plan:', e);
                }
              } else {
                store.setDraftPhase('REVIEW');
                if (data.planVersion !== undefined) {
                  store.setPlanVersion(data.planVersion);
                }
                if (data.toolPlanId) {
                  store.setCurrentToolPlanId(String(data.toolPlanId));
                }
              }

              store.setIsGenerating(false);
              store.setAbortController(null);
              toast.success('설계안 생성이 완료되었습니다.');
              disconnectSSE();
              break;

            case 'TOOL_GENERATION_COMPLETED':
              if (flow === 'PLAN') break;

              store.setProgressInfo({
                step: '완료',
                message: data.message || 'Tool 빌드가 완료되었습니다.',
                percent: 100,
              });

              if (data.toolId) {
                store.setCurrentToolId(String(data.toolId));
              }
              if (data.draftVersion !== undefined) {
                store.setDraftVersion(data.draftVersion);
              }
              if (data.draftPhase) {
                store.setDraftPhase(data.draftPhase as DraftPhase);
              }
              
              store.setIsBuilding(false);
              store.setIsGenerating(false);
              store.setAbortController(null);
              toast.success('도구 빌드가 완료되었습니다.');
              disconnectSSE();
              break;

            case 'ERROR': {
              store.setIsGenerating(false);
              store.setIsBuilding(false);
              store.setAbortController(null);

              const errorMsg = data.errorMessage || 'Tool 생성에 실패했습니다.';
              toast.error(errorMsg);

              store.addMessage({
                messageId: crypto.randomUUID(),
                senderType: 'SYSTEM_NOTICE',
                content: `생성 실패: ${errorMsg}`,
                createdAt: new Date().toISOString(),
              });
              disconnectSSE();
              break;
            }

            default:
              console.warn('[SSE] Unknown event type:', rawEventType, data);
          }
        } catch {
          console.warn('[SSE] Failed to parse event data:', ev.data);
        }
      },

      onerror(err) {
        console.error('[SSE] Connection error:', err);
        const store = useChatSessionStore.getState();
        store.setIsGenerating(false);
        store.setIsBuilding(false);
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
