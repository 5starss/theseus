import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ChatDashboard } from '@/features/projects/components/chat/ChatDashboard';
import { chatApi } from '@/features/projects/api/chat';
import { useChatSessionStore } from '@/features/projects/stores/useChatSessionStore';
import type { ChatMessage, StructuredPlan, DraftPhase } from '@/features/projects/types/chat';

export default function ChatSessionPage() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const [isLoading, setIsLoading] = useState(true);
  const initSession = useChatSessionStore(state => state.initSession);

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
  }, [projectId, sessionId, initSession]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#051424] text-slate-500">
        세션 데이터를 불러오는 중입니다...
      </div>
    );
  }

  return <ChatDashboard />;
}

