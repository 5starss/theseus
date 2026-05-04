import { NavLink, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  MessageSquarePlus,
  Wrench,
  Settings,
  UserCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import { projectApi, type ProjectMemberResponse } from '@/features/projects/api';
import { chatApi } from '@/features/projects/api/chat';
import { useAuthStore } from '@/store/useAuthStore';
import type { ChatSession } from '@/features/projects/types/chat';

interface SidebarProps {
  projectId?: string;
}

export function Sidebar({ projectId }: SidebarProps) {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [projectMember, setProjectMember] = useState<ProjectMemberResponse | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSessionsLoading, setIsSessionsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  const refetchSessions = () => setFetchTrigger(n => n + 1);

  useEffect(() => {
    let cancelled = false;
    const fetchMemberInfo = async () => {
      if (!projectId) {
        if (!cancelled) setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const memberData = await projectApi.getProjectMe(projectId);
        if (cancelled) return;
        setProjectMember(memberData);
      } catch (err: unknown) {
        if (!cancelled) {
          console.error('Failed to fetch project member info:', err);
          const axiosErr = err as { response?: { data?: { message?: string } }; message?: string };
          setErrorMessage(axiosErr.response?.data?.message || axiosErr.message || '인증 오류가 발생했습니다.');
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    fetchMemberInfo();
    return () => { cancelled = true; };
  }, [projectId]);

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

  const displayRole = isLoading
    ? 'Loading...'
    : projectMember
      ? getRoleLabel(projectMember.projectRole)
      : (errorMessage || 'Access Denied');

  return (
    <aside className="w-[260px] h-screen shrink-0 bg-[rgba(17,24,39,0.8)] backdrop-blur-[12px] border-r border-[#1f2937] flex flex-col pt-6 z-20 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)] relative">

      {/* Brand Section */}
      <div className="px-6 mb-8 flex items-center gap-3">
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
          ) : sessions.length > 0 ? (
            sessions.map((session) => (
              <li key={session.sessionId}>
                <NavLink
                  to={`/projects/${projectId}/sessions/${session.sessionId}`}
                  className={({ isActive }) => cn(
                    "block w-full px-3 py-2 rounded text-xs tracking-[0.35px] truncate transition-colors",
                    isActive
                      ? "bg-white/10 text-white font-medium"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-300"
                  )}
                >
                  {session.title}
                </NavLink>
              </li>
            ))
          ) : (
            <li className="px-3 py-2 text-[10px] text-slate-500 italic">
              생성된 세션이 없습니다.
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
  );
}
