import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Plus, Edit2 } from 'lucide-react';
import { memberApi } from '@/features/projects/api/member';
import type { ProjectMemberResponse } from '@/features/projects/api';
import { AddMemberModal } from './AddMemberModal';
import { EditMemberModal } from './EditMemberModal';

interface ProjectMemberManagementProps {
  projectId: string;
}

export function ProjectMemberManagement({ projectId }: ProjectMemberManagementProps) {
  const [members, setMembers] = useState<ProjectMemberResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  // States for Add Member Dialog
  const [isAddOpen, setIsAddOpen] = useState(false);

  // States for Edit Member Dialog
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<ProjectMemberResponse | null>(null);

  const refetch = () => setFetchTrigger(n => n + 1);

  useEffect(() => {
    let cancelled = false;
    const fetchMembers = async () => {
      setIsLoading(true);
      try {
        const res = await memberApi.getMembers(projectId, 0, 100, 'ALL');
        if (cancelled) return;

        // 다중 정렬: 상태(진행 중 우선) -> 역할(ADMIN > MANAGER > MEMBER) -> 레벨(내림차순) -> 이름(오름차순)
        const sorted = (res || []).sort((a, b) => {
          // 1. 상태 (진행 중 우선)
          if (a.status !== b.status) {
            return a.status === 'IN_PROGRESS' ? -1 : 1;
          }

          // 2. 역할 (ADMIN > MANAGER > MEMBER)
          const roleOrder: Record<string, number> = { ADMIN: 0, MANAGER: 1, MEMBER: 2 };
          const aOrder = roleOrder[a.projectRole] ?? 99;
          const bOrder = roleOrder[b.projectRole] ?? 99;
          if (aOrder !== bOrder) {
            return aOrder - bOrder;
          }

          // 3. 레벨 (내림차순)
          if (a.accessLevel !== b.accessLevel) {
            return b.accessLevel - a.accessLevel;
          }

          // 4. 이름 (오름차순)
          return (a.name || '').localeCompare(b.name || '');
        });

        setMembers(sorted);
      } catch (err) {
        if (!cancelled) console.error('Failed to fetch members', err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchMembers();
    return () => { cancelled = true; };
  }, [projectId, fetchTrigger]);

  const openEditModal = (member: ProjectMemberResponse) => {
    setSelectedMember(member);
    setIsEditOpen(true);
  };

  const getRoleBadgeStyles = () => {
    return "bg-slate-800/40 text-slate-300 border-slate-700/50 ring-1 ring-slate-800/50";
  };

  return (
    <Card className="bg-slate-900/40 backdrop-blur-xl border-slate-800 shadow-2xl shadow-blue-500/5 overflow-x-auto">
      <CardHeader className="flex flex-row items-center justify-between border-b border-slate-800/50 mb-6 min-w-[900px]">
        <div className="min-w-max">
          <CardTitle className="text-white font-['Space_Grotesk'] mb-1 whitespace-nowrap">멤버 관리</CardTitle>
          <CardDescription className="text-slate-400 whitespace-nowrap">프로젝트에 참여 중인 멤버와 권한을 관리합니다.</CardDescription>
        </div>

        <Button className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold flex items-center gap-2" onClick={() => setIsAddOpen(true)}>
          <Plus className="w-4 h-4" /> 멤버 추가
        </Button>
        <AddMemberModal
          projectId={projectId}
          isOpen={isAddOpen}
          onOpenChange={setIsAddOpen}
          onSuccess={refetch}
        />
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div className="py-12 text-center text-slate-500 animate-pulse">멤버 목록을 불러오는 중...</div>
        ) : (
          <div className="border border-slate-800 rounded-lg overflow-x-auto bg-slate-950/20">
            <Table className="min-w-[900px]">
              <TableHeader className="bg-slate-950/50">
                <TableRow className="border-slate-800 hover:bg-transparent">
                  <TableHead className="w-[180px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">이름 / 사번</TableHead>
                  <TableHead className="w-[160px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">역할 / 레벨</TableHead>
                  <TableHead className="w-[300px] text-center text-slate-400 font-bold uppercase text-[10px] tracking-widest pl-4">도구 권한</TableHead>
                  <TableHead className="w-[120px] text-center text-slate-400 font-bold uppercase text-[10px] tracking-widest">상태</TableHead>
                  <TableHead className="w-[80px] text-center text-slate-400 font-bold uppercase text-[10px] tracking-widest">관리</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.length === 0 ? (
                  <TableRow className="border-slate-800 hover:bg-slate-900/20">
                    <TableCell colSpan={5} className="text-center py-12 text-slate-500 font-medium">
                      등록된 멤버가 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  members.map(member => (
                    <TableRow key={member.projectMemberId} className="border-slate-800 hover:bg-slate-900/40 transition-colors">
                      <TableCell>
                        <div className="font-bold text-slate-200">{member.name}</div>
                        <div className="text-xs text-slate-500 font-mono mt-0.5">{member.employeeNumber}</div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className={cn("font-bold tracking-tight px-2 py-0.5 border-transparent flex items-center gap-1.5", getRoleBadgeStyles())}>
                            {member.projectRole}
                          </Badge>
                          <span className="text-[10px] text-slate-500 font-bold whitespace-nowrap">
                            LV.{member.accessLevel}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1.5 flex-wrap pl-4">
                          {member.canUseTool && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-slate-800 bg-slate-900/50 text-slate-400 uppercase font-bold tracking-tight">
                              Use
                            </Badge>
                          )}
                          {member.canCreateTool && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-slate-800 bg-slate-900/50 text-slate-400 uppercase font-bold tracking-tight">
                              Create
                            </Badge>
                          )}
                          {member.canUpdateTool && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-slate-800 bg-slate-900/50 text-slate-400 uppercase font-bold tracking-tight">
                              Update
                            </Badge>
                          )}
                          {member.canDeleteTool && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-slate-800 bg-slate-900/50 text-slate-400 uppercase font-bold tracking-tight">
                              Delete
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant={member.status === 'IN_PROGRESS' ? 'default' : 'secondary'} className={cn(
                          "font-bold text-[10px]",
                          member.status === 'IN_PROGRESS' ? "bg-blue-400 text-[#003a6b] hover:bg-blue-400" : "bg-slate-800 text-slate-400 hover:bg-slate-800"
                        )}>
                          {member.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Button variant="ghost" size="sm" onClick={() => openEditModal(member)} className="text-slate-400 hover:text-blue-400 hover:bg-blue-400/10">
                          <Edit2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>

      {isEditOpen && selectedMember && (
        <EditMemberModal
          key={selectedMember.projectMemberId}
          projectId={projectId}
          isOpen={isEditOpen}
          onOpenChange={setIsEditOpen}
          onSuccess={refetch}
          selectedMember={selectedMember}
        />
      )}
    </Card>
  );
}
