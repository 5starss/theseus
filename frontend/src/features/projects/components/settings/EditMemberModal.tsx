import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { ShieldAlert } from 'lucide-react';
import { memberApi } from '@/features/projects/api/member';
import type { ProjectMemberResponse } from '@/features/projects/api';
import type { ProjectMemberUpdateRequest } from '@/features/projects/types/member';

const DEFAULT_MEMBER_ACCESS_LEVEL = 1;
const MAX_MEMBER_ACCESS_LEVEL = 5;
const ADMIN_ACCESS_LEVEL = 5;

const clampMemberAccessLevel = (value: number) =>
  Math.min(MAX_MEMBER_ACCESS_LEVEL, Math.max(DEFAULT_MEMBER_ACCESS_LEVEL, value));

interface EditMemberModalProps {
  projectId: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
  selectedMember: ProjectMemberResponse | null;
}

export function EditMemberModal({ projectId, isOpen, onOpenChange, onSuccess, selectedMember }: EditMemberModalProps) {
  const [editRole, setEditRole] = useState<'ADMIN' | 'MANAGER' | 'MEMBER'>(selectedMember?.projectRole ?? 'MEMBER');
  const [editAccessLevel, setEditAccessLevel] = useState(
    selectedMember?.projectRole === 'ADMIN'
      ? ADMIN_ACCESS_LEVEL
      : clampMemberAccessLevel(selectedMember?.accessLevel ?? DEFAULT_MEMBER_ACCESS_LEVEL)
  );
  const [editCanCreate, setEditCanCreate] = useState(selectedMember?.canCreateTool ?? false);
  const [editCanUse, setEditCanUse] = useState(selectedMember?.canUseTool ?? true);
  const [editCanUpdate, setEditCanUpdate] = useState(selectedMember?.canUpdateTool ?? false);
  const [editCanDelete, setEditCanDelete] = useState(selectedMember?.canDeleteTool ?? false);
  const [editStatus, setEditStatus] = useState<'IN_PROGRESS' | 'COMPLETED'>(selectedMember?.status ?? 'IN_PROGRESS');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRoleChange = (role: 'ADMIN' | 'MANAGER' | 'MEMBER') => {
    setEditRole(role);
    if (role === 'ADMIN') {
      setEditAccessLevel(ADMIN_ACCESS_LEVEL);
      return;
    }
    if (editRole === 'ADMIN') {
      setEditAccessLevel(DEFAULT_MEMBER_ACCESS_LEVEL);
      return;
    }
    setEditAccessLevel(clampMemberAccessLevel(editAccessLevel));
  };

  const handleEditMember = async () => {
    if (!selectedMember) return;
    setIsSubmitting(true);
    try {
      const data: ProjectMemberUpdateRequest = {
        projectRole: editRole,
        accessLevel: editRole === 'ADMIN' ? ADMIN_ACCESS_LEVEL : clampMemberAccessLevel(editAccessLevel),
        canCreateTool: editCanCreate,
        canUseTool: editCanUse,
        canUpdateTool: editCanUpdate,
        canDeleteTool: editCanDelete,
        status: editStatus,
      };
      await memberApi.updateMember(projectId, selectedMember.projectMemberId, data);
      toast.success('멤버 정보가 성공적으로 변경되었습니다.');
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      console.error('Update member failed', err);
      toast.error('멤버 수정에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md bg-[#0b1424] border-slate-800 text-slate-100">
        <DialogHeader>
          <DialogTitle className="text-white">멤버 권한 수정</DialogTitle>
          <DialogDescription className="text-slate-400">
            {selectedMember?.name} ({selectedMember?.employeeNumber}) 님의 권한을 수정합니다.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-6 py-4">
          {selectedMember?.projectRole === 'ADMIN' && (
            <div className="bg-blue-400/10 border border-blue-400/20 rounded-md p-3 flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
              <p className="text-[12px] text-blue-300 leading-relaxed">
                프로젝트 담당자 변경은 시스템 관리자만 가능합니다.
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-slate-300 uppercase text-[10px] tracking-wider">역할 (Role)</Label>
              {selectedMember?.projectRole === 'ADMIN' ? (
                <div className="bg-slate-950 border border-slate-800 text-blue-400 font-bold h-10 rounded-md px-3 flex items-center text-sm">
                  ADMIN
                </div>
              ) : (
                <Select value={editRole} onValueChange={(v: 'MEMBER' | 'MANAGER' | 'ADMIN') => handleRoleChange(v)}>
                  <SelectTrigger className="bg-slate-950 border-slate-800 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-800 text-white">
                    <SelectItem value="MEMBER">Member</SelectItem>
                    <SelectItem value="MANAGER">Manager</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300 uppercase text-[10px] tracking-wider">레벨 (Access Level)</Label>
              <input
                type="number"
                min={DEFAULT_MEMBER_ACCESS_LEVEL}
                max={MAX_MEMBER_ACCESS_LEVEL}
                value={editRole === 'ADMIN' ? ADMIN_ACCESS_LEVEL : editAccessLevel}
                disabled={editRole === 'ADMIN' || selectedMember?.projectRole === 'ADMIN'}
                onChange={(e) => setEditAccessLevel(clampMemberAccessLevel(Number(e.target.value)))}
                className="bg-slate-950 border-slate-800 text-white h-10 rounded-md px-3 text-sm w-full focus:ring-1 focus:ring-blue-400 outline-none"
              />
              <p className="text-[11px] text-slate-500">Member/Manager/Admin: 1-5</p>
            </div>
          </div>

          <div className="space-y-4 border border-slate-800 rounded-lg p-4 bg-slate-950/30">
            <Label className="flex items-center gap-2 mb-2 text-blue-400 font-bold text-[11px] uppercase tracking-wider"><ShieldAlert className="w-3.5 h-3.5" /> 도구 권한 세부 설정</Label>
            <div className="flex items-center justify-between">
              <Label htmlFor="canUse" className="text-slate-300">사용 권한 (Can Use)</Label>
              <Switch
                id="canUse"
                checked={editCanUse}
                onCheckedChange={setEditCanUse}
                disabled={selectedMember?.projectRole === 'ADMIN'}
                className="data-[state=checked]:bg-blue-400"
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="canCreate" className="text-slate-300">생성 권한 (Can Create)</Label>
              <Switch
                id="canCreate"
                checked={editCanCreate}
                onCheckedChange={setEditCanCreate}
                disabled={selectedMember?.projectRole === 'ADMIN'}
                className="data-[state=checked]:bg-blue-400"
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="canUpdate" className="text-slate-300">수정 권한 (Can Update)</Label>
              <Switch
                id="canUpdate"
                checked={editCanUpdate}
                onCheckedChange={setEditCanUpdate}
                disabled={selectedMember?.projectRole === 'ADMIN'}
                className="data-[state=checked]:bg-blue-400"
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="canDelete" className="text-slate-300">삭제 권한 (Can Delete)</Label>
              <Switch
                id="canDelete"
                checked={editCanDelete}
                onCheckedChange={setEditCanDelete}
                disabled={selectedMember?.projectRole === 'ADMIN'}
                className="data-[state=checked]:bg-blue-400"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-slate-300 uppercase text-[10px] tracking-wider">멤버 상태 (Status)</Label>
            <Select
              value={editStatus}
              onValueChange={(v: 'IN_PROGRESS' | 'COMPLETED') => setEditStatus(v)}
              disabled={selectedMember?.projectRole === 'ADMIN'}
            >
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
          <Button variant="outline" onClick={() => onOpenChange(false)} className="border-slate-700 text-slate-300 hover:bg-slate-800">취소</Button>
          <Button onClick={handleEditMember} disabled={isSubmitting} className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold">
            {isSubmitting ? '저장 중...' : '변경사항 저장'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
