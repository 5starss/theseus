import { useParams } from 'react-router-dom';
import { ChatDashboard } from '@/features/projects/components/chat/ChatDashboard';
import { useChatSessionLoader } from '@/features/projects/hooks/useChatSessionLoader';

export default function ChatSessionPage() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const { isLoading } = useChatSessionLoader(projectId, sessionId);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#051424] text-slate-500">
        세션 데이터를 불러오는 중입니다...
      </div>
    );
  }

  return <ChatDashboard />;
}
