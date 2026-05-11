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
  const setCurrentToolPlanId = useChatSessionStore(state => state.setCurrentToolPlanId);
  const setPlanVersion = useChatSessionStore(state => state.setPlanVersion);
  const setIsBuilding = useChatSessionStore(state => state.setIsBuilding);
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
          
          let currentToolIdVal = (details.currentToolId as string) || null;
          let currentToolPlanIdVal = (details.currentToolPlanId as string) || null;

          // 복구 로직: DTO에 값이 없는 경우 히스토리에서 추출
          if (!currentToolIdVal && !currentToolPlanIdVal && messages.length > 0) {
            const lastToolMessage = [...messages].reverse().find(m => m.toolId);
            if (lastToolMessage) {
              currentToolIdVal = String(lastToolMessage.toolId);
              currentToolPlanIdVal = String(lastToolMessage.toolId); // 백엔드 이전 데이터 호환성용
            }
          }

          let loadedPhase: DraftPhase = (details.draftPhase as DraftPhase) || null;
          let loadedDraftVersion = (details.draftVersion as number) || 0;
          let loadedPlanVersion = (details.planVersion as number) || 0;
          let loadedPlan = (details.currentPlan as StructuredPlan) || null;

          if (currentToolIdVal) {
            try {
              const toolDetail = await toolApi.getTool(projectId, currentToolIdVal);
              if (toolDetail && isMounted) {
                if (toolDetail.structuredPlanJson) {
                  try {
                    loadedPlan = JSON.parse(toolDetail.structuredPlanJson);
                  } catch (e) {
                    console.error('Failed to parse structuredPlanJson:', e);
                  }
                }
                loadedPhase = toolDetail.draftPhase;
                loadedDraftVersion = toolDetail.draftVersion;
                // planVersion은 API에 없다면 임시로 draftVersion 사용
                loadedPlanVersion = toolDetail.draftVersion;
              }
            } catch (err) {
              console.warn('Failed to load tool detail for recovery:', err);
            }
          }

          initSession({
            messages,
            plan: loadedPlan,
            phase: loadedPhase,
            toolId: currentToolIdVal,
            toolPlanId: currentToolPlanIdVal,
            toolResult: (details.draftSnapshot as Record<string, unknown>) || null,
            title: (details.title as string) || '새 세션',
            isClosed: (details.isClosed as boolean) || false,
            planVersion: loadedPlanVersion,
            draftVersion: loadedDraftVersion,
          });

          // 생성 중단 상태 복구 로직 (새로고침 시)
          if (currentToolIdVal || currentToolPlanIdVal) {
            try {
              // 1. 빌드 상태 조회
              if (currentToolIdVal) {
                const stateResult = await chatApi.getToolGenerationState(projectId, sessionId, currentToolIdVal);
                
                if ((stateResult.status === 'GENERATING' || stateResult.status === 'IN_PROGRESS') && isMounted) {
                  setIsGenerating(true);
                  setIsBuilding(true);
                  setProgressInfo({
                    step: stateResult.message || '빌드 중...',
                    message: stateResult.message || '',
                    percent: stateResult.progressRate ?? 0,
                  });
                  if (stateResult.content) {
                    updateLastMessageContent(stateResult.content);
                  }
                  const sseUrl = `/api/v1/projects/${projectId}/sessions/${sessionId}/tools/${currentToolIdVal}/generation-state/stream`;
                  connectSSE(sseUrl, 'BUILD', Number(currentToolIdVal));
                  return; // 빌드 중이면 Plan 상태 복구는 스킵
                }
              }

              // 2. 설계 상태 조회
              if (currentToolPlanIdVal) {
                const planStateResult = await chatApi.getToolPlanGenerationState(projectId, sessionId, currentToolPlanIdVal);
                if ((planStateResult.status === 'GENERATING' || planStateResult.status === 'IN_PROGRESS') && isMounted) {
                  setIsGenerating(true);
                  setProgressInfo({
                    step: planStateResult.message || '설계안 생성 중...',
                    message: planStateResult.message || '',
                    percent: planStateResult.progressRate ?? 0,
                  });
                  if (planStateResult.content) {
                    updateLastMessageContent(planStateResult.content);
                  }
                  const sseUrl = `/api/v1/projects/${projectId}/sessions/${sessionId}/tool-plans/${currentToolPlanIdVal}/generation-state/stream`;
                  connectSSE(sseUrl, 'PLAN', planStateResult.runId);
                }
              }
            } catch (stateError) {
              console.warn('진행 중인 생성 작업 확인 실패 (정상적인 종료 상태일 수 있음):', stateError);
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
  }, [projectId, sessionId, initSession, setIsGenerating, setIsBuilding, setProgressInfo, updateLastMessageContent, connectSSE, setCurrentPlan, setCurrentToolId, setCurrentToolPlanId, setDraftPhase, setDraftVersion, setPlanVersion]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#051424] text-slate-500">
        세션 데이터를 불러오는 중입니다...
      </div>
    );
  }

  return <ChatDashboard />;
}

