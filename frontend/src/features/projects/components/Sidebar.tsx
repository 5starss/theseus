import { NavLink, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  MessageSquarePlus,
  Wrench,
  Settings,
  UserCircle,
  MoreVertical,
  Pencil,
  Trash2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import { projectApi } from '@/features/projects/api';
import { useProjectStore } from '../stores/useProjectStore';
import { chatApi } from '@/features/projects/api/chat';
import { useAuthStore } from '@/store/useAuthStore';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import type { ChatSession } from '@/features/projects/types/chat';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface SidebarProps {
  projectId?: string;
}

export function Sidebar({ projectId }: SidebarProps) {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { currentProject: projectMember, isLoading: isProjectLoading, errorMessage: projectErrorMessage } = useProjectStore();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isSessionsLoading, setIsSessionsLoading] = useState(false);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  // Rename Modal States
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [editingSession, setEditingSession] = useState<{ id: number; title: string } | null>(null);
  const [tempTitle, setTempTitle] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);

  const refetchSessions = () => setFetchTrigger(n => n + 1);


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
  }, [projectId, fetchTrigger]);

  const handleNewChat = async () => {
    if (!projectId) return;
    try {
      const session = await chatApi.createSession(projectId);
      if (session && session.sessionId) {
        // 세션 목록 갱신
        refetchSessions();
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
    setTempTitle(currentTitle);
    setIsRenameModalOpen(true);
  };

  const confirmRename = async () => {
    if (!tempTitle || !tempTitle.trim() || !editingSession || !projectId) return;
    if (tempTitle.trim() === editingSession.title) {
      setIsRenameModalOpen(false);
      return;
    }

    setIsRenaming(true);
    try {
      await chatApi.updateSessionTitle(projectId, editingSession.id.toString(), tempTitle.trim());
      setSessions(prev => prev.map(s => s.sessionId === editingSession.id ? { ...s, title: tempTitle.trim() } : s));

      // 만약 현재 활성화된 세션이라면 전역 스토어도 업데이트
      const currentActiveSessionId = window.location.pathname.split('/').pop();
      if (currentActiveSessionId === editingSession.id.toString()) {
        useChatSessionStore.getState().updateTitle(tempTitle.trim());
      }
      setIsRenameModalOpen(false);
    } catch (err) {
      console.error('Failed to rename session:', err);
      alert('이름 수정에 실패했습니다.');
    } finally {
      setIsRenaming(false);
    }
  };

  const handleCloseSession = async (sessionId: number) => {
    if (!projectId || !window.confirm('이 세션을 종료하시겠습니까?')) return;

    try {
      await chatApi.closeSession(projectId, sessionId.toString());
      setSessions(prev => prev.map(s => s.sessionId === sessionId ? { ...s, isClosed: true } : s));

      // 만약 현재 활성화된 세션이라면 전역 스토어도 업데이트
      const currentActiveSessionId = window.location.pathname.split('/').pop();
      if (currentActiveSessionId === sessionId.toString()) {
        useChatSessionStore.getState().setClosed(true);
        useChatSessionStore.getState().addMessage({
          id: crypto.randomUUID(),
          sender: 'SYSTEM_NOTICE',
          content: '이 세션이 종료되었습니다.',
          createdAt: new Date().toISOString()
        });
      }
    } catch (err) {
      console.error('Failed to close session:', err);
      alert('세션 종료에 실패했습니다.');
    }
  };

  const isAdmin = projectMember?.projectRole === 'ADMIN';
  const displayName = projectMember?.name || user?.name || 'User';

  const getRoleLabel = (role?: string) => {
    switch (role) {
      case 'ADMIN': return 'Project Admin';
      case 'MANAGER': return 'Project Manager';
      case 'MEMBER': return 'Project Member';
      default: return 'No Role';
    }
  };

  const displayRole = isProjectLoading
    ? 'Loading...'
    : projectMember
      ? getRoleLabel(projectMember.projectRole)
      : (projectErrorMessage || 'Access Denied');

  const activeSessions = sessions.filter(s => !s.isClosed);

  return (
    <>
      <aside className="w-[260px] h-screen shrink-0 bg-[rgba(17,24,39,0.8)] backdrop-blur-[12px] border-r border-[#1f2937] flex flex-col pt-6 z-20 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)] relative">

        {/* Brand Section */}
        <div
          className="px-6 mb-8 flex items-center gap-3 cursor-pointer group transition-all duration-200 active:scale-[0.98]"
          onClick={() => navigate('/')}
        >
          <div className="w-8 h-8 rounded bg-blue-400 flex items-center justify-center shrink-0">
            <Sparkles className="w-4 h-4 text-[#003a6b]" />
          </div>
          <div className="flex flex-col">
            <h1 className="font-['Space_Grotesk'] font-bold text-xl text-blue-400 tracking-[-1px] leading-tight" style={{ textShadow: '0px 0px 10px rgba(96,165,250,0.4)' }}>
              Theseus
            </h1>
            <span className="font-['Space_Grotesk'] font-normal text-[10px] text-slate-500 tracking-[1px] uppercase">
              AI LAB SYSTEM
            </span>
          </div>
        </div>

        {/* Primary Actions */}
        <div className="px-4 mb-6">
          <button
            onClick={handleNewChat}
            className="w-full bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-medium text-xs tracking-[0.6px] uppercase py-2 rounded flex items-center justify-center transition-colors"
          >
            새 대화
          </button>
        </div>

        {/* Nav Tabs */}
        <nav className="flex flex-col gap-1 mb-8">
          <NavLink
            to={`/projects/${projectId}/tools`}
            className={({ isActive }) => cn(
              "flex items-center gap-3 px-6 py-3 transition-colors border-l-4",
              isActive
                ? "bg-[#1e293b] border-blue-400 text-blue-400"
                : "border-transparent text-slate-400 hover:bg-white/5 hover:text-slate-300"
            )}
          >
            <Wrench className="w-4 h-4 ml-0.5" />
            <span className="text-sm font-medium tracking-[0.35px]">도구 목록</span>
          </NavLink>
        </nav >

        {/* Conversation Sessions List */}
        < div className="flex-1 overflow-y-auto px-4 flex flex-col gap-3 min-h-0" >
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

                  {/* Dropdown Menu Trigger - Visible on hover */}
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
        </div >

        {/* Footer Section */}
        < div className="mt-auto px-6 pb-6 pt-4 flex flex-col gap-4 border-t border-[rgba(31,41,55,0.5)]" >
          {isAdmin && (
            <NavLink
              to={`/projects/${projectId}/settings`}
              className={({ isActive }) => cn(
                "flex items-center gap-3 py-2 transition-colors",
                isActive ? "text-blue-400" : "text-slate-400 hover:text-slate-300"
              )}
            >
              <Settings className="w-4 h-4" />
              <span className="text-sm font-medium tracking-[0.35px]">관리자 설정</span>
            </NavLink>
          )
          }

          <div className="flex items-center gap-3 p-3 rounded bg-white/5">
            <div className="w-8 h-8 rounded-full border border-blue-400/20 overflow-hidden shrink-0 flex items-center justify-center bg-slate-800">
              <UserCircle className="w-6 h-6 text-slate-400" />
            </div>
            <div className="flex flex-col min-w-0 flex-1">
              <span className="font-bold text-xs text-slate-100 tracking-[0.35px] truncate">
                {displayName}
              </span>
              <span className="font-['Space_Grotesk'] text-[10px] text-slate-500 tracking-[0.35px] truncate">
                {displayRole}
              </span>
            </div>
          </div>
        </div >
      </aside >

      {/* Rename Modal */}
      <Dialog open={isRenameModalOpen} onOpenChange={setIsRenameModalOpen}>
        <DialogContent className="bg-[#0b1424] border-slate-800 text-slate-100 sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-blue-400 font-['Space_Grotesk']">세션 이름 수정</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Input
              value={tempTitle}
              onChange={(e) => setTempTitle(e.target.value)}
              placeholder="세션 이름을 입력하세요"
              className="bg-slate-900/50 border-slate-700 text-slate-200 focus:border-blue-400"
              onKeyDown={(e) => {
                if (e.key === 'Enter') confirmRename();
              }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setIsRenameModalOpen(false)}
              className="text-slate-400 hover:text-slate-100 hover:bg-white/5"
            >
              취소
            </Button>
            <Button
              onClick={confirmRename}
              disabled={isRenaming || !tempTitle.trim() || tempTitle.trim() === editingSession?.title}
              className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold"
            >
              {isRenaming ? '저장 중...' : '저장'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
