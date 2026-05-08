import { NavLink, useNavigate } from 'react-router-dom';
import { Sparkles, Wrench, Settings, UserCircle, LogOut, User, Key, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useProjectStore } from '../stores/useProjectStore';
import { useAuthStore } from '@/store/useAuthStore';
import { SessionList } from './SessionList';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const PermissionItem = ({ label, active }: { label: string; active?: boolean }) => (
  <div className="flex items-center gap-1.5">
    {active ? (
      <Check className="w-2.5 h-2.5 text-blue-400" />
    ) : (
      <X className="w-2.5 h-2.5 text-slate-600" />
    )}
    <span className={cn(
      "text-[9px] font-medium tracking-tight",
      active ? "text-slate-300" : "text-slate-600"
    )}>
      {label}
    </span>
  </div>
);

interface SidebarProps {
  projectId?: string;
}

export function Sidebar({ projectId }: SidebarProps) {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
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

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <div className="flex items-center gap-3 p-3 rounded bg-white/5 cursor-pointer border border-transparent">
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
            </DropdownMenuTrigger>
            <DropdownMenuContent
              side="top"
              align="start"
              sideOffset={12}
              className="w-[220px] bg-[#0b1424] border-slate-800 text-slate-200 p-2 shadow-2xl backdrop-blur-xl"
            >
              <DropdownMenuLabel className="px-3 py-3">
                <div className="flex flex-col gap-2">
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">User Profile</span>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-blue-400/10 flex items-center justify-center border border-blue-400/20">
                      <UserCircle className="w-6 h-6 text-blue-400" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <span className="text-sm font-bold text-slate-100 truncate">{displayName}</span>
                      <span className="text-[10px] text-slate-400 font-['Space_Grotesk'] tracking-tight truncate">
                        {projectMember?.employeeNumber || 'ID: ' + user?.id}
                      </span>
                    </div>
                  </div>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-slate-800/50" />

              <div className="px-1 py-2">
                <div className="px-2 py-1 flex flex-col gap-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[10px] text-slate-400">
                      <Key className="w-3.5 h-3.5 text-blue-400" />
                      <span className="font-medium">Access Level</span>
                    </div>
                    <span className="text-[10px] font-bold text-slate-100 font-['Space_Grotesk']">
                      Lv.{projectMember?.accessLevel || 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[10px] text-slate-400">
                      <User className="w-3.5 h-3.5 text-blue-400" />
                      <span className="font-medium">Project Role</span>
                    </div>
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-400/20 text-slate-100 font-bold border border-blue-400/30">
                      {projectMember?.projectRole || 'MEMBER'}
                    </span>
                  </div>
                </div>
              </div>

              <DropdownMenuSeparator className="bg-slate-800/50" />

              <div className="px-3 py-2">
                <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold mb-2 block">Tool Permissions</span>
                <div className="grid grid-cols-2 gap-2">
                  <PermissionItem label="Use" active={projectMember?.canUseTool} />
                  <PermissionItem label="Create" active={projectMember?.canCreateTool} />
                  <PermissionItem label="Update" active={projectMember?.canUpdateTool} />
                  <PermissionItem label="Delete" active={projectMember?.canDeleteTool} />
                </div>
              </div>

              <DropdownMenuSeparator className="bg-slate-800/50" />
              <DropdownMenuItem
                onClick={() => logout()}
                className="flex items-center gap-2 px-3 py-2.5 text-red-400 hover:text-red-300 focus:text-red-300 focus:bg-red-400/10 cursor-pointer transition-colors rounded-sm group/item"
              >
                <LogOut className="w-4 h-4 transition-transform group-hover/item:-translate-x-0.5" />
                <span className="text-xs font-bold uppercase tracking-wider">Logout</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div >
      </aside >


    </>
  );
}
