import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { chatApi } from '@/features/projects/api/chat';
import { useProjectStore } from '@/features/projects/stores/useProjectStore';

export default function ProjectIndexPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const refreshSessions = useProjectStore((state) => state.refreshSessions);

  useEffect(() => {
    let cancelled = false;
    const redirectLogic = async () => {
      if (!projectId) return;

      try {
        // 1. 세션 목록 조회 (최신순으로 조회)
        const sessionsData = await chatApi.getSessions(projectId, 0, 10);
        if (cancelled) return;

        // 2. 활성화된(isClosed: false) 세션 중 가장 최근 것 찾기
        const latestActiveSession = sessionsData.content.find(s => !s.isClosed);

        if (latestActiveSession) {
          // 활성 세션이 있으면 해당 세션으로 이동
          navigate(`/projects/${projectId}/sessions/${latestActiveSession.sessionId}`, { replace: true });
        } else {
          // 3. 활성 세션이 하나도 없으면 새 세션 생성 후 이동
          const newSession = await chatApi.createSession(projectId);
          if (cancelled) return;
          
          // 사이드바 세션 목록 갱신 트리거
          refreshSessions();
          
          navigate(`/projects/${projectId}/sessions/${newSession.sessionId}`, { replace: true });
        }
      } catch (error) {
        console.error('Failed to redirect to session:', error);
        // 에러 발생 시 세션 목록 대기 페이지로 이동
        navigate(`/projects/${projectId}/sessions`, { replace: true });
      }
    };

    redirectLogic();
    return () => { cancelled = true; };
  }, [projectId, navigate]);

  return (
    <div className="flex-1 flex items-center justify-center bg-[#010f1f]">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400 animate-pulse text-sm">대화 세션에 연결 중입니다...</p>
      </div>
    </div>
  );
}
