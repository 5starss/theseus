import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ChatDashboard } from '@/features/projects/components/chat/ChatDashboard';
import { chatApi } from '@/features/projects/api/chat';
import { toolApi } from '@/features/tools/api';
import { useChatSessionStore } from '@/features/projects/stores/useChatSessionStore';
import { useToolGenerationSSE } from '@/features/projects/hooks/useToolGenerationSSE';
import type { ChatMessage, StructuredPlan, DraftPhase } from '@/features/projects/types/chat';

export default function ChatSessionPage() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const [isLoading, setIsLoading] = useState(true);
  const initSession = useChatSessionStore(state => state.initSession);
  const setIsGenerating = useChatSessionStore(state => state.setIsGenerating);
  const setProgressInfo = useChatSessionStore(state => state.setProgressInfo);
  const setCurrentToolId = useChatSessionStore(state => state.setCurrentToolId);
  const setCurrentPlan = useChatSessionStore(state => state.setCurrentPlan);
  const setDraftPhase = useChatSessionStore(state => state.setDraftPhase);
  const setDraftVersion = useChatSessionStore(state => state.setDraftVersion);
  const updateLastMessageContent = useChatSessionStore(state => state.updateLastMessageContent);
  const { connectSSE } = useToolGenerationSSE();

  useEffect(() => {
    let isMounted = true;

    const loadSession = async () => {
      if (!projectId || !sessionId) return;
      setIsLoading(true);
      try {
        const result = await chatApi.getSessionDetails(projectId, sessionId);
        if (isMounted) {
          const details = result as Record<string, unknown>;
          const messages = (details.messages as ChatMessage[]) || [];
          
          initSession({
            messages,
            plan: (details.currentPlan as StructuredPlan) || null,
            phase: (details.draftPhase as DraftPhase) || null,
            toolId: (details.currentToolId as string) || null,
            toolResult: (details.draftSnapshot as Record<string, unknown>) || null,
            title: (details.title as string) || '새 세션',
            isClosed: (details.isClosed as boolean) || false
          });

          // 복구 로직: DTO에 currentToolId가 없는 경우 메시지 히스토리에서 추출
          let currentToolIdVal = details.currentToolId as string;
          if (!currentToolIdVal && messages.length > 0) {
            const lastToolMessage = [...messages].reverse().find(m => m.toolId);
            if (lastToolMessage) {
              currentToolIdVal = String(lastToolMessage.toolId);
            }
          }

          if (currentToolIdVal) {
            try {
              // 1. 우선 Redis/진행 상태 조회
              const stateResult = await chatApi.getToolGenerationState(projectId, sessionId, currentToolIdVal);
              
              if (stateResult.status === 'GENERATING' && isMounted) {
                // 생성 중인 경우: SSE 재연결 및 진행바 표시
                setIsGenerating(true);
                setProgressInfo({
                  step: stateResult.message || '생성 중...',
                  message: stateResult.message || '',
                  percent: stateResult.progressRate ?? 0,
                });
                if (stateResult.content) {
                  updateLastMessageContent(stateResult.content);
                }
                
                const sseUrl = `/api/v1/projects/${projectId}/sessions/${sessionId}/tools/${currentToolIdVal}/events`;
                connectSSE(sseUrl, Number(currentToolIdVal));
              } else if ((stateResult.status === 'REVIEW' || stateResult.status === 'DRAFT') && isMounted) {
                // 이미 생성이 완료되었거나 중단된 경우: DB에서 전체 Plan 정보(structuredPlanJson)를 가져와서 UI 복구
                const toolDetail = await toolApi.getTool(projectId, currentToolIdVal);
                if (toolDetail && isMounted) {
                  if (toolDetail.structuredPlanJson) {
                    try {
                      const planObj = JSON.parse(toolDetail.structuredPlanJson);
                      setCurrentPlan(planObj);
                    } catch (e) {
                      console.error('Failed to parse structuredPlanJson:', e);
                    }
                  }
                  setDraftPhase(toolDetail.draftPhase);
                  setDraftVersion(toolDetail.draftVersion);
                  setCurrentToolId(currentToolIdVal);
                }
              }
            } catch (stateError) {
              console.error('Failed to restore generation state:', stateError);
            }
          }
        }
      } catch (error) {
        console.error('Failed to load chat session details:', error);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    loadSession();

    return () => {
      isMounted = false;
    };
  }, [projectId, sessionId, initSession, setIsGenerating, setProgressInfo, updateLastMessageContent, connectSSE, setCurrentPlan, setCurrentToolId, setDraftPhase, setDraftVersion]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#051424] text-slate-500">
        세션 데이터를 불러오는 중입니다...
      </div>
    );
  }

  return <ChatDashboard />;
}

