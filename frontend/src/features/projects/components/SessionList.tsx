import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { MessageSquarePlus, MoreVertical, Pencil, Trash2, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { chatApi } from '@/features/projects/api/chat';
import { useProjectStore } from '../stores/useProjectStore';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import type { ChatSession } from '@/features/projects/types/chat';
import { RenameSessionModal } from './RenameSessionModal';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface SessionListProps {
  projectId: string | undefined;
  children?: React.ReactNode;
  isCollapsed?: boolean;
}

export function SessionList({ projectId, children, isCollapsed }: SessionListProps) {
  const navigate = useNavigate();
  const { sessionFetchTrigger, refreshSessions } = useProjectStore();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isSessionsLoading, setIsSessionsLoading] = useState(false);

  // Rename Modal States
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [editingSession, setEditingSession] = useState<{ id: number; title: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsSessionsLoading(true);
      try {
        const res = await chatApi.getSessions(projectId);
        if (cancelled) return;
        setSessions(res.content);
      } catch (err) {
        if (!cancelled) console.error('Failed to load sessions', err);
      } finally {
        if (!cancelled) setIsSessionsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [projectId, sessionFetchTrigger]);

  const handleNewChat = async () => {
    if (!projectId) return;
    try {
      const session = await chatApi.createSession(projectId);
      if (session && session.sessionId) {
        refreshSessions();
        navigate(`/projects/${projectId}/sessions/${session.sessionId}`);
      } else {
        navigate(`/projects/${projectId}/sessions/new`);
      }
    } catch (err) {
      console.error('Failed to create session:', err);
      alert('세션 생성에 실패했습니다.');
    }
  };

  const handleRenameSession = (sessionId: number, currentTitle: string) => {
    setEditingSession({ id: sessionId, title: currentTitle });
    setIsRenameModalOpen(true);
  };

  const confirmRename = async (newTitle: string) => {
    if (!editingSession || !projectId) return;
    try {
      await chatApi.updateSessionTitle(projectId, editingSession.id.toString(), newTitle);
      setSessions(prev => prev.map(s => s.sessionId === editingSession.id ? { ...s, title: newTitle } : s));

      const currentActiveSessionId = window.location.pathname.split('/').pop();
      if (currentActiveSessionId === editingSession.id.toString()) {
        useChatSessionStore.getState().updateTitle(newTitle);
      }
      setIsRenameModalOpen(false);
    } catch (err) {
      console.error('Failed to rename session:', err);
      alert('이름 수정에 실패했습니다.');
    }
  };

  const handleCloseSession = async (sessionId: number) => {
    if (!projectId || !window.confirm('이 세션을 종료하시겠습니까?')) return;

    try {
      await chatApi.closeSession(projectId, sessionId.toString());
      setSessions(prev => prev.map(s => s.sessionId === sessionId ? { ...s, isClosed: true } : s));

      const currentActiveSessionId = window.location.pathname.split('/').pop();
      if (currentActiveSessionId === sessionId.toString()) {
        useChatSessionStore.getState().setClosed(true);
        // 종료 후 프로젝트 인덱스로 이동하여 새 세션 생성/찾기 로직 트리거
        navigate(`/projects/${projectId}`, { replace: true });
      }
    } catch (err) {
      console.error('Failed to close session:', err);
      alert('세션 종료에 실패했습니다.');
    }
  };

  const activeSessions = sessions.filter(s => !s.isClosed);

  return (
    <>
      <div className={cn(isCollapsed ? "px-1 mb-6 flex justify-center" : "px-4 mb-6")}>
        {isCollapsed ? (
          <button
            onClick={handleNewChat}
            className="w-10 h-10 bg-blue-400 hover:bg-blue-500 text-[#003a6b] rounded-full flex items-center justify-center transition-all duration-200 shadow-md active:scale-95 cursor-pointer"
            title="새 대화"
          >
            <Plus className="w-5 h-5" />
          </button>
        ) : (
          <button
            onClick={handleNewChat}
            className="w-full bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-medium text-xs tracking-[0.6px] uppercase py-2 rounded flex items-center justify-center transition-colors active:scale-[0.98] cursor-pointer"
          >
            새 대화
          </button>
        )}
      </div>

      {children}

      {!isCollapsed && (
        <div className="flex-1 overflow-y-auto px-4 flex flex-col gap-3 min-h-0">
          <div className="flex items-center gap-2 px-2 shrink-0">
            <MessageSquarePlus className="w-3 h-3 text-slate-500" />
            <h3 className="text-[10px] font-medium text-slate-500 uppercase tracking-[1px]">
              대화 세션 목록
            </h3>
          </div>
          <ul className="flex flex-col gap-1">
            {isSessionsLoading ? (
            <li className="px-3 py-2 text-[10px] text-slate-500 animate-pulse">
              세션 목록 로딩 중...
            </li>
          ) : activeSessions.length > 0 ? (
            activeSessions.map((session) => (
              <li key={session.sessionId} className="group relative">
                <NavLink
                  to={`/projects/${projectId}/sessions/${session.sessionId}`}
                  className={({ isActive }) => cn(
                    "flex items-center justify-between w-full px-3 py-2 rounded text-xs tracking-[0.35px] transition-colors",
                    isActive
                      ? "bg-white/10 text-white font-medium"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-300"
                  )}
                >
                  <span className="truncate flex-1">{session.title}</span>
                </NavLink>

                <div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="p-1 hover:text-white text-slate-500 rounded transition-colors">
                        <MoreVertical size={14} />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="bg-[#0b0e14] border-slate-800 text-slate-300 min-w-[100px]">
                      <DropdownMenuItem
                        onClick={() => handleRenameSession(session.sessionId, session.title)}
                        className="flex items-center gap-2 text-xs focus:bg-white/5 focus:text-white cursor-pointer"
                      >
                        <Pencil size={12} />
                        <span>이름 수정</span>
                      </DropdownMenuItem>
                      {!session.isClosed && (
                        <DropdownMenuItem
                          onClick={() => handleCloseSession(session.sessionId)}
                          className="flex items-center gap-2 text-xs focus:bg-red-500/10 focus:text-red-400 text-red-400/80 cursor-pointer"
                        >
                          <Trash2 size={12} />
                          <span>세션 종료</span>
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </li>
            ))
          ) : (
            <li className="px-3 py-2 text-[10px] text-slate-500 italic">
              활성 세션이 없습니다.
            </li>
          )}
        </ul>
      </div>
      )}

      {isRenameModalOpen && editingSession && (
        <RenameSessionModal
          key={editingSession.id}
          isOpen={isRenameModalOpen}
          onClose={() => setIsRenameModalOpen(false)}
          onConfirm={confirmRename}
          initialTitle={editingSession.title}
        />
      )}
    </>
  );
}
