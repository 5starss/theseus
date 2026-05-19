import { useCallback, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { toast } from 'sonner';
import { useAuthStore } from '@/store/useAuthStore';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import { chatApi } from '../api/chat';
import { parseStructuredPlanJson } from '../utils/structuredPlan';
import type { DraftPhase, ToolGenerationSseEvent } from '../types/chat';

function normalizeEventType(eventName?: string, payloadEventType?: string) {
  const rawEventType = eventName || payloadEventType || '';
  return rawEventType.toLowerCase();
}

function phaseFromStatus(status?: string | null): DraftPhase {
  switch (status) {
    case 'REQUESTED':
    case 'GENERATING':
      return 'PLAN';
    case 'REVIEW':
      return 'REVIEW';
    case 'PENDING':
      return 'PENDING';
    case 'APPROVED':
      return 'APPROVED';
    case 'REJECTED':
      return 'REJECTED';
    case 'BUILDING':
      return 'BUILDING';
    case 'BUILT':
      return 'BUILT';
    case 'FAILED':
      return 'FAILED';
    default:
      return null;
  }
}

function planStatusFrom(status?: string | null) {
  return status === 'SKIPPED' ? null : status || null;
}

const PLAN_PROGRESS_MESSAGES: Record<string, string> = {
  REQUEST_RECEIVED: 'PLAN 요청을 접수했습니다.',
  PLAN_DRAFTING: 'PLAN 초안을 작성하고 있습니다.',
  PLAN_STRUCTURING: 'PLAN 구조를 정규화하고 표시 형식으로 정리하고 있습니다.',
  PLAN_FEEDBACK: '검증 결과를 바탕으로 사용자 안내를 준비하고 있습니다.',
  PLAN_VALIDATING: 'PLAN 스냅샷과 실행 명세를 검증하고 있습니다.',
  PLAN_COMPLETED: 'PLAN 초안이 준비되었습니다.',
};

function displayProgressMessage(message?: string) {
  if (!message) return '';
  return PLAN_PROGRESS_MESSAGES[message] || message;
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
    if (connectedStreamRef.current === streamId && abortRef.current) {
      return;
    }
    if (connectedStreamRef.current && connectedStreamRef.current !== streamId) {
      disconnectSSE();
    }
    connectedStreamRef.current = streamId;

    const controller = new AbortController();
    abortRef.current = controller;

    const store = useChatSessionStore.getState();
    if (flow === 'BUILD') {
      store.setIsBuilding(true);
      store.setIsGenerating(false);
    } else {
      store.setIsGenerating(true);
      store.setIsBuilding(false);
    }

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

          // Check if the event belongs to the current project and session
          if (
            (data.projectId !== undefined && String(data.projectId) !== String(projectId))
            || (data.chatSessionId !== undefined && String(data.chatSessionId) !== String(sessionId))
          ) {
            console.log(`[SSE] Ignoring event for different session: proj=${data.projectId}, sess=${data.chatSessionId}`);
            return;
          }

          const eventType = normalizeEventType(ev.event, data.eventType);
          const store = useChatSessionStore.getState();

          switch (eventType) {
            case 'connected':
              console.log('[SSE] Connected to ToolPlan stream', data);
              break;

            case 'progress': {
              const message = displayProgressMessage(data.message);
              const step = flow === 'PLAN'
                ? 'PLAN 생성 중'
                : (message || 'Tool build in progress');
              store.setProgressInfo({
                step,
                message,
                percent: data.progressRate ?? 0,
              });
              break;
            }

            case 'chunk':
              if (data.content) {
                if (data.replay) {
                  store.replaceLastMessageContent(data.content);
                } else {
                  store.updateLastMessageContent(data.content);
                }
              }
              break;

            case 'completed':
            case 'tool_plan_completed':
            case 'tool_build_completed':
              if (flow === 'BUILD') {
                store.setIsBuilding(false);
                store.setIsGenerating(false);
                store.setProgressInfo({
                  step: 'Completed',
                  message: data.message || 'Tool build completed.',
                  percent: 100,
                });
                if (data.toolId) {
                  store.setCurrentToolId(String(data.toolId));
                }
                toast.success('Tool build completed.');

                if (projectId && sessionId) {
                  try {
                    const details = await chatApi.getSessionDetails(projectId, sessionId);
                    const toolPlanId = details.currentPlan?.toolPlanId || data.toolPlanId || null;
                    const toolPlanGroupId = details.currentPlan?.toolPlanGroupId || data.toolPlanGroupId || null;
                    const detail = toolPlanId
                      ? await chatApi.getToolPlanDetail(projectId, sessionId, String(toolPlanId))
                      : null;
                    const phase = details.createdTool
                      ? phaseFromStatus(details.createdTool.status) || 'BUILT'
                      : phaseFromStatus(details.currentPlan?.status) || 'REVIEW';

                    store.initSession({
                      messages: details.messages || [],
                      plan: parseStructuredPlanJson(detail?.structuredPlanJson, 'SSE') || store.currentPlan,
                      phase,
                      toolId: details.createdTool?.toolId ? String(details.createdTool.toolId) : null,
                      toolPlanGroupId: toolPlanGroupId ? String(toolPlanGroupId) : null,
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
                  } catch (error) {
                    console.error('[SSE] Failed to refresh session details for tool build completed:', error);
                  }
                }

                disconnectSSE();
                break;
              }

              store.setProgressInfo({
                step: 'Completed',
                message: data.message || 'Tool PLAN generation completed.',
                percent: 100,
              });

              if (projectId && sessionId) {
                try {
                  const details = await chatApi.getSessionDetails(projectId, sessionId);
                  const toolPlanId = details.currentPlan?.toolPlanId || data.toolPlanId || null;
                  const toolPlanGroupId = details.currentPlan?.toolPlanGroupId || data.toolPlanGroupId || null;
                  const detail = toolPlanId
                    ? await chatApi.getToolPlanDetail(projectId, sessionId, String(toolPlanId))
                    : null;
                  const phase = details.createdTool
                    ? phaseFromStatus(details.createdTool.status) || 'BUILT'
                    : phaseFromStatus(details.currentPlan?.status) || 'REVIEW';

                  store.initSession({
                    messages: details.messages || [],
                    plan: parseStructuredPlanJson(detail?.structuredPlanJson, 'SSE') || store.currentPlan,
                    phase,
                    toolId: details.createdTool?.toolId ? String(details.createdTool.toolId) : null,
                    toolPlanGroupId: toolPlanGroupId ? String(toolPlanGroupId) : null,
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
                } catch (error) {
                  console.error('[SSE] Failed to refresh session details for plan:', error);
                  store.setDraftPhase('REVIEW');
                  store.setPlanStatus('REVIEW');
                }
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
              toast.success('Tool PLAN generation completed.');
              disconnectSSE();
              break;

            case 'skipped':
            case 'tool_plan_skipped': {
              store.setIsGenerating(false);
              store.setIsBuilding(false);
              store.setDraftPhase(null);
              store.setPlanStatus(null);
              store.setProgressInfo(null);
              store.setAbortController(null);
              store.setCurrentRunId(null);

              const chatMessage = {
                messageId: crypto.randomUUID(),
                senderType: 'ASSISTANT',
                messageType: 'CHAT',
                contentType: 'TEXT',
                content: data.message || 'This request was handled as a general chat message.',
                createdAt: new Date().toISOString(),
              } as const;

              if (projectId && sessionId) {
                try {
                  const details = await chatApi.getSessionDetails(projectId, sessionId);
                  const toolPlanId = details.currentPlan?.toolPlanId || null;
                  const detail = toolPlanId
                    ? await chatApi.getToolPlanDetail(projectId, sessionId, String(toolPlanId))
                    : null;
                  const phase = details.createdTool
                    ? phaseFromStatus(details.createdTool.status) || 'BUILT'
                    : phaseFromStatus(details.currentPlan?.status);

                  store.initSession({
                    messages: details.messages || [],
                    plan: parseStructuredPlanJson(detail?.structuredPlanJson, 'SSE') || null,
                    phase,
                    toolId: details.createdTool?.toolId ? String(details.createdTool.toolId) : null,
                    toolPlanGroupId: details.currentPlan?.toolPlanGroupId ? String(details.currentPlan.toolPlanGroupId) : null,
                    toolPlanId: toolPlanId ? String(toolPlanId) : null,
                    runId: null,
                    planStatus: planStatusFrom(details.currentPlan?.status),
                    createdTool: details.createdTool,
                    toolResult: details.createdTool ? { ...details.createdTool } : null,
                    title: details.title || store.title,
                    isClosed: details.isClosed || false,
                    planVersion: details.currentPlan?.planVersion || detail?.planVersion || 0,
                    draftVersion: details.currentPlan?.planVersion || detail?.planVersion || 0,
                  });
                } catch (error) {
                  console.warn('[SSE] Failed to refresh skipped ToolPlan response:', error);
                  store.completeAssistantPlaceholder(chatMessage);
                }
              } else {
                store.completeAssistantPlaceholder(chatMessage);
              }

              disconnectSSE();
              break;
            }

            case 'failed':
            case 'tool_plan_failed':
            case 'tool_build_failed': {
              store.setIsGenerating(false);
              store.setIsBuilding(false);
              store.setDraftPhase('FAILED');
              store.setPlanStatus('FAILED');
              store.setAbortController(null);

              const errorMessage = data.errorMessage || data.message || 'Tool PLAN generation failed.';
              toast.error(errorMessage);
              store.addMessage({
                messageId: crypto.randomUUID(),
                senderType: 'SYSTEM_NOTICE',
                messageType: 'SYSTEM_NOTICE',
                contentType: 'TEXT',
                content: `Generation failed: ${errorMessage}`,
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
        toast.error('SSE connection was lost.');
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
  }, [disconnectSSE, projectId, sessionId]);

  return { connectSSE, disconnectSSE };
}
