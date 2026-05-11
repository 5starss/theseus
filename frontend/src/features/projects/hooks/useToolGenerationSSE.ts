import { useCallback, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { toast } from 'sonner';
import { useAuthStore } from '@/store/useAuthStore';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import { chatApi } from '../api/chat';
import type { StructuredPlan, ToolGenerationSseEvent } from '../types/chat';

function parseStructuredPlan(structuredPlanJson?: string | null): StructuredPlan | null {
  if (!structuredPlanJson) return null;

  try {
    const parsed = JSON.parse(structuredPlanJson) as StructuredPlan;
    return Array.isArray(parsed.blocks) ? parsed : null;
  } catch (error) {
    console.warn('[SSE] Failed to parse ToolPlan detail:', error);
    return null;
  }
}

function normalizeEventType(eventName?: string, payloadEventType?: string) {
  const rawEventType = eventName || payloadEventType || '';
  return rawEventType.toLowerCase();
}

export function useToolGenerationSSE() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const abortRef = useRef<AbortController | null>(null);
  const connectedStreamRef = useRef<string | null>(null);

  const disconnectSSE = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    connectedStreamRef.current = null;
  }, []);

  const connectSSE = useCallback((sseUrl: string, flow: 'PLAN' | 'BUILD', id?: string | number) => {
    const streamId = id == null ? sseUrl : String(id);
    if (connectedStreamRef.current && connectedStreamRef.current !== streamId) {
      disconnectSSE();
    }
    connectedStreamRef.current = streamId;

    const controller = new AbortController();
    abortRef.current = controller;

    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
    const fullUrl = sseUrl.startsWith('http') ? sseUrl : `${baseUrl}${sseUrl}`;
    const token = useAuthStore.getState().accessToken;

    fetchEventSource(fullUrl, {
      method: 'GET',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        Accept: 'text/event-stream',
      },
      signal: controller.signal,
      openWhenHidden: true,

      async onmessage(ev) {
        if (!ev.data) return;

        try {
          const data: ToolGenerationSseEvent = JSON.parse(ev.data);
          const eventType = normalizeEventType(ev.event, data.eventType);
          const store = useChatSessionStore.getState();

          switch (eventType) {
            case 'connected':
              console.log('[SSE] Connected to ToolPlan stream', data);
              break;

            case 'progress':
              store.setProgressInfo({
                step: data.message || 'PLAN 생성 중',
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
            case 'tool_plan_completed':
            case 'tool_build_completed':
              if (flow === 'BUILD') {
                store.setIsBuilding(false);
                store.setIsGenerating(false);
                store.setProgressInfo({
                  step: '완료',
                  message: data.message || 'Tool 생성이 완료되었습니다.',
                  percent: 100,
                });
                if (data.toolId) {
                  store.setCurrentToolId(String(data.toolId));
                }
                toast.success('Tool 생성이 완료되었습니다.');
                disconnectSSE();
                break;
              }

              store.setProgressInfo({
                step: '완료',
                message: data.message || 'Tool PLAN 생성이 완료되었습니다.',
                percent: 100,
              });

              if (projectId && sessionId) {
                const details = await chatApi.getSessionDetails(projectId, sessionId);
                const toolPlanId = details.currentPlan?.toolPlanId || data.toolPlanId || null;
                const detail = toolPlanId
                  ? await chatApi.getToolPlanDetail(projectId, sessionId, String(toolPlanId))
                  : null;

                store.initSession({
                  messages: details.messages || [],
                  plan: parseStructuredPlan(detail?.structuredPlanJson),
                  phase: 'REVIEW',
                  toolId: details.createdTool?.toolId ? String(details.createdTool.toolId) : null,
                  toolPlanGroupId: details.currentPlan?.toolPlanGroupId ? String(details.currentPlan.toolPlanGroupId) : null,
                  toolPlanId: toolPlanId ? String(toolPlanId) : null,
                  runId: details.currentPlan?.runId || data.runId || null,
                  planStatus: details.currentPlan?.status || 'REVIEW',
                  createdTool: details.createdTool,
                  toolResult: details.createdTool ? { ...details.createdTool } : null,
                  title: details.title || store.title,
                  isClosed: details.isClosed || false,
                  planVersion: details.currentPlan?.planVersion || detail?.planVersion || data.planVersion || store.planVersion,
                  draftVersion: details.currentPlan?.planVersion || detail?.planVersion || store.draftVersion,
                });
              } else {
                store.setDraftPhase('REVIEW');
                store.setPlanStatus('REVIEW');
                if (data.planVersion !== undefined) {
                  store.setPlanVersion(data.planVersion);
                }
                if (data.toolPlanId) {
                  store.setCurrentToolPlanId(String(data.toolPlanId));
                }
              }

              store.setIsGenerating(false);
              store.setAbortController(null);
              toast.success('Tool PLAN 생성이 완료되었습니다.');
              disconnectSSE();
              break;

            case 'skipped':
            case 'tool_plan_skipped':
              store.setIsGenerating(false);
              store.setDraftPhase(null);
              store.setPlanStatus('SKIPPED');
              store.setAbortController(null);
              store.addMessage({
                messageId: crypto.randomUUID(),
                senderType: 'ASSISTANT',
                messageType: 'CHAT',
                contentType: 'TEXT',
                content: data.message || '이 요청은 Tool PLAN 생성 대상이 아닙니다.',
                createdAt: new Date().toISOString(),
              });
              toast.info('Tool PLAN 생성 없이 안내 메시지로 처리되었습니다.');
              disconnectSSE();
              break;

            case 'failed':
            case 'tool_plan_failed':
            case 'tool_build_failed': {
              store.setIsGenerating(false);
              store.setIsBuilding(false);
              store.setDraftPhase('FAILED');
              store.setPlanStatus('FAILED');
              store.setAbortController(null);

              const errorMessage = data.errorMessage || data.message || 'Tool PLAN 생성에 실패했습니다.';
              toast.error(errorMessage);
              store.addMessage({
                messageId: crypto.randomUUID(),
                senderType: 'SYSTEM_NOTICE',
                messageType: 'SYSTEM_NOTICE',
                contentType: 'TEXT',
                content: `생성 실패: ${errorMessage}`,
                createdAt: new Date().toISOString(),
              });
              disconnectSSE();
              break;
            }

            default:
              console.warn('[SSE] Unknown event type:', eventType, data);
          }
        } catch (error) {
          console.warn('[SSE] Failed to handle event data:', ev.data, error);
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
        throw err;
      },

      onclose() {
        console.log('[SSE] Connection closed');
      },
    });

    useChatSessionStore.getState().setAbortController(controller);
  }, [disconnectSSE, projectId, sessionId]);

  useEffect(() => {
    return () => {
      disconnectSSE();
    };
  }, [disconnectSSE]);

  return { connectSSE, disconnectSSE };
}
