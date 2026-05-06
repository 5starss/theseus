import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Plus, Edit2, ShieldAlert } from 'lucide-react';
import { memberApi } from '@/features/projects/api/member';
import type { ProjectMemberResponse } from '@/features/projects/api';
import type { ProjectMemberCreateRequest, ProjectMemberUpdateRequest } from '@/features/projects/types/member';

interface ProjectMemberManagementProps {
  projectId: string;
}

export function ProjectMemberManagement({ projectId }: ProjectMemberManagementProps) {
  const [members, setMembers] = useState<ProjectMemberResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  // States for Add Member Dialog
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newEmployeeNumber, setNewEmployeeNumber] = useState('');
  const [newRole, setNewRole] = useState<'ADMIN' | 'MANAGER' | 'MEMBER'>('MEMBER');

  // States for Edit Member Dialog
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<ProjectMemberResponse | null>(null);
  const [editRole, setEditRole] = useState<'ADMIN' | 'MANAGER' | 'MEMBER'>('MEMBER');
  const [editAccessLevel, setEditAccessLevel] = useState(1);
  const [editCanCreate, setEditCanCreate] = useState(false);
  const [editCanUse, setEditCanUse] = useState(true);
  const [editCanUpdate, setEditCanUpdate] = useState(false);
  const [editCanDelete, setEditCanDelete] = useState(false);
  const [editStatus, setEditStatus] = useState<'IN_PROGRESS' | 'COMPLETED'>('IN_PROGRESS');

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

  const handleAddMember = async () => {
    try {
      const data: ProjectMemberCreateRequest = {
        employeeNumber: newEmployeeNumber,
        projectRole: newRole,
        accessLevel: 1,
        canCreateTool: newRole === 'ADMIN' || newRole === 'MANAGER',
        canUseTool: true,
        canUpdateTool: newRole === 'ADMIN' || newRole === 'MANAGER',
        canDeleteTool: newRole === 'ADMIN',
      };
      await memberApi.addMember(projectId, data);
      setIsAddOpen(false);
      setNewEmployeeNumber('');
      setNewRole('MEMBER');
      refetch();
    } catch (err: unknown) {
      console.error('Add member failed', err);
      const axiosErr = err as { response?: { data?: { message?: string } } };
      alert(axiosErr.response?.data?.message || '멤버 추가에 실패했습니다. 사번을 확인해주세요.');
    }
  };

  const openEditModal = (member: ProjectMemberResponse) => {
    setSelectedMember(member);
    setEditRole(member.projectRole);
    setEditAccessLevel(member.accessLevel);
    setEditCanCreate(member.canCreateTool);
    setEditCanUse(member.canUseTool);
    setEditCanUpdate(member.canUpdateTool);
    setEditCanDelete(member.canDeleteTool);
    setEditStatus(member.status);
    setIsEditOpen(true);
  };

  const handleEditMember = async () => {
    if (!selectedMember) return;
    try {
      const data: ProjectMemberUpdateRequest = {
        projectRole: editRole,
        accessLevel: editAccessLevel,
        canCreateTool: editCanCreate,
        canUseTool: editCanUse,
        canUpdateTool: editCanUpdate,
        canDeleteTool: editCanDelete,
        status: editStatus,
      };
      await memberApi.updateMember(projectId, selectedMember.projectMemberId, data);
      setIsEditOpen(false);
      refetch();
    } catch (err) {
      console.error('Update member failed', err);
      alert('멤버 수정에 실패했습니다.');
    }
  };

  const getRoleBadgeStyles = (_role: string) => {
    return "bg-slate-800/40 text-slate-300 border-slate-700/50 ring-1 ring-slate-800/50";
  };

  return (
    <Card className="bg-slate-900/40 backdrop-blur-xl border-slate-800 shadow-2xl shadow-blue-500/5 overflow-x-auto">
      <CardHeader className="flex flex-row items-center justify-between border-b border-slate-800/50 mb-6 min-w-[900px]">
        <div className="min-w-max">
          <CardTitle className="text-white font-['Space_Grotesk'] mb-1 whitespace-nowrap">멤버 관리</CardTitle>
          <CardDescription className="text-slate-400 whitespace-nowrap">프로젝트에 참여 중인 멤버와 권한을 관리합니다.</CardDescription>
        </div>

        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold flex items-center gap-2">
              <Plus className="w-4 h-4" /> 멤버 추가
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#0b1424] border-slate-800 text-slate-100">
            <DialogHeader>
              <DialogTitle className="text-white">새 멤버 추가</DialogTitle>
              <DialogDescription className="text-slate-400">
                사용자의 사번을 입력하여 프로젝트 멤버로 초대합니다.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="employeeNumber" className="text-slate-300 uppercase text-[10px] tracking-wider">사번 (Employee Number)</Label>
                <Input
                  id="employeeNumber"
                  placeholder="예: 082XXXX"
                  value={newEmployeeNumber}
                  onChange={(e) => setNewEmployeeNumber(e.target.value)}
                  className="bg-slate-950 border-slate-800 text-white"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-slate-300 uppercase text-[10px] tracking-wider">역할 할당</Label>
                <Select value={newRole} onValueChange={(v: 'MEMBER' | 'MANAGER' | 'ADMIN') => setNewRole(v)}>
                  <SelectTrigger className="bg-slate-950 border-slate-800 text-white">
                    <SelectValue placeholder="역할 선택" />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800 text-white">
                    <SelectItem value="MEMBER">Member</SelectItem>
                    <SelectItem value="MANAGER">Manager</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsAddOpen(false)} className="border-slate-700 text-slate-300 hover:bg-slate-800">취소</Button>
              <Button onClick={handleAddMember} disabled={!newEmployeeNumber} className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold">추가하기</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
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
                          <Badge variant="outline" className={cn("font-bold tracking-tight px-2 py-0.5 border-transparent flex items-center gap-1.5", getRoleBadgeStyles(member.projectRole))}>
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

      {/* Edit Member Dialog */}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="max-w-md bg-[#0b1424] border-slate-800 text-slate-100">
          <DialogHeader>
            <DialogTitle className="text-white">멤버 권한 수정</DialogTitle>
            <DialogDescription className="text-slate-400">
              {selectedMember?.name} ({selectedMember?.employeeNumber}) 님의 권한을 수정합니다.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-slate-300 uppercase text-[10px] tracking-wider">역할 (Role)</Label>
                <Select value={editRole} onValueChange={(v: 'MEMBER' | 'MANAGER' | 'ADMIN') => setEditRole(v)}>
                  <SelectTrigger className="bg-slate-950 border-slate-800 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800 text-white">
                    <SelectItem value="MEMBER">Member</SelectItem>
                    <SelectItem value="MANAGER">Manager</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-slate-300 uppercase text-[10px] tracking-wider">레벨 (Access Level)</Label>
                <input
                  type="number"
                  min={1}
                  max={99}
                  value={editAccessLevel}
                  onChange={(e) => setEditAccessLevel(Number(e.target.value))}
                  className="bg-slate-950 border-slate-800 text-white h-10 rounded-md px-3 text-sm w-full"
                />
              </div>
            </div>

            <div className="space-y-4 border border-slate-800 rounded-lg p-4 bg-slate-950/30">
              <Label className="flex items-center gap-2 mb-2 text-blue-400 font-bold text-[11px] uppercase tracking-wider"><ShieldAlert className="w-3.5 h-3.5" /> 도구 권한 세부 설정</Label>
              <div className="flex items-center justify-between">
                <Label htmlFor="canUse" className="text-slate-300">사용 권한 (Can Use)</Label>
                <Switch id="canUse" checked={editCanUse} onCheckedChange={setEditCanUse} className="data-[state=checked]:bg-blue-400" />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="canCreate" className="text-slate-300">생성 권한 (Can Create)</Label>
                <Switch id="canCreate" checked={editCanCreate} onCheckedChange={setEditCanCreate} className="data-[state=checked]:bg-blue-400" />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="canUpdate" className="text-slate-300">수정 권한 (Can Update)</Label>
                <Switch id="canUpdate" checked={editCanUpdate} onCheckedChange={setEditCanUpdate} className="data-[state=checked]:bg-blue-400" />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="canDelete" className="text-slate-300">삭제 권한 (Can Delete)</Label>
                <Switch id="canDelete" checked={editCanDelete} onCheckedChange={setEditCanDelete} className="data-[state=checked]:bg-blue-400" />
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300 uppercase text-[10px] tracking-wider">멤버 상태 (Status)</Label>
              <Select value={editStatus} onValueChange={(v: 'IN_PROGRESS' | 'COMPLETED') => setEditStatus(v)}>
                <SelectTrigger className="bg-slate-950 border-slate-800 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-800 text-white">
                  <SelectItem value="IN_PROGRESS">활동 중 (IN_PROGRESS)</SelectItem>
                  <SelectItem value="COMPLETED">활동 완료 (COMPLETED)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditOpen(false)} className="border-slate-700 text-slate-300 hover:bg-slate-800">취소</Button>
            <Button onClick={handleEditMember} className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold">변경사항 저장</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
