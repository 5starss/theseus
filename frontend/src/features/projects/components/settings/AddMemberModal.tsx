import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { memberApi } from '@/features/projects/api/member';
import type { ProjectMemberCreateRequest } from '@/features/projects/types/member';

interface AddMemberModalProps {
  projectId: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function AddMemberModal({ projectId, isOpen, onOpenChange, onSuccess }: AddMemberModalProps) {
  const [newEmployeeNumber, setNewEmployeeNumber] = useState('');
  const [newRole, setNewRole] = useState<'ADMIN' | 'MANAGER' | 'MEMBER'>('MEMBER');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAddMember = async () => {
    setIsSubmitting(true);
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
      onOpenChange(false);
      setNewEmployeeNumber('');
      setNewRole('MEMBER');
      onSuccess();
    } catch (err: unknown) {
      console.error('Add member failed', err);
      const axiosErr = err as { response?: { data?: { message?: string } } };
      alert(axiosErr.response?.data?.message || '멤버 추가에 실패했습니다. 사번을 확인해주세요.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
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
          <Button variant="outline" onClick={() => onOpenChange(false)} className="border-slate-700 text-slate-300 hover:bg-slate-800">취소</Button>
          <Button onClick={handleAddMember} disabled={!newEmployeeNumber || isSubmitting} className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold">
            {isSubmitting ? '추가 중...' : '추가하기'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
