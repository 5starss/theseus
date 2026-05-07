import { NavLink, useNavigate } from 'react-router-dom';
import { Sparkles, Wrench, Settings, UserCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useProjectStore } from '../stores/useProjectStore';
import { useAuthStore } from '@/store/useAuthStore';
import { SessionList } from './SessionList';

interface SidebarProps {
  projectId?: string;
}

export function Sidebar({ projectId }: SidebarProps) {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { currentProject: projectMember, isLoading: isProjectLoading, errorMessage: projectErrorMessage } = useProjectStore();

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

        <SessionList projectId={projectId}>
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
        </SessionList>

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


    </>
  );
}
