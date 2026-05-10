import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ChatDashboard } from '@/features/projects/components/chat/ChatDashboard';
import { chatApi } from '@/features/projects/api/chat';
import { useChatSessionStore } from '@/features/projects/stores/useChatSessionStore';
import { useToolGenerationSSE } from '@/features/projects/hooks/useToolGenerationSSE';
import type { ChatMessage, StructuredPlan, DraftPhase } from '@/features/projects/types/chat';

export default function ChatSessionPage() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const [isLoading, setIsLoading] = useState(true);
  const initSession = useChatSessionStore(state => state.initSession);
  const setIsGenerating = useChatSessionStore(state => state.setIsGenerating);
  const setProgressInfo = useChatSessionStore(state => state.setProgressInfo);
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
          initSession({
            messages: (details.messages as ChatMessage[]) || [],
            plan: (details.currentPlan as StructuredPlan) || null,
            phase: (details.draftPhase as DraftPhase) || null,
            toolId: (details.currentToolId as string) || null,
            toolResult: (details.draftSnapshot as Record<string, unknown>) || null,
            title: (details.title as string) || '새 세션',
            isClosed: (details.isClosed as boolean) || false
          });

          // 복구 로직: 현재 진행 중인 Tool이 있는지 확인
          const currentToolId = details.currentToolId as string;
          if (currentToolId) {
            try {
              const stateResult = await chatApi.getToolGenerationState(projectId, sessionId, currentToolId);
              if (stateResult.status === 'GENERATING' && isMounted) {
                setIsGenerating(true);
                setProgressInfo({
                  step: stateResult.message || '생성 중...',
                  message: stateResult.message || '',
                  percent: stateResult.progressRate ?? 0,
                });
                if (stateResult.content) {
                  // 기존 내용이 store.messages에 포함되어 있을 수 있으므로 바로 덮어쓰거나 무시할지 결정.
                  // 최신 content를 반영하기 위해 빈 값 전송 후 업데이트
                  updateLastMessageContent(stateResult.content);
                }
                
                // SSE 재연결
                const sseUrl = `/api/v1/projects/${projectId}/sessions/${sessionId}/tools/${currentToolId}/events`;
                connectSSE(sseUrl, Number(currentToolId));
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
  }, [projectId, sessionId, initSession, setIsGenerating, setProgressInfo, updateLastMessageContent, connectSSE]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#051424] text-slate-500">
        세션 데이터를 불러오는 중입니다...
      </div>
    );
  }

  return <ChatDashboard />;
}

