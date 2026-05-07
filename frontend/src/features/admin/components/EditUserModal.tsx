import { useState } from 'react';
import { adminApi } from '../api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface EditUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  userId: number | null;
  initialName: string;
  initialEmail: string;
}

export function EditUserModal({ isOpen, onClose, onSuccess, userId, initialName, initialEmail }: EditUserModalProps) {
  const [editUserForm, setEditUserForm] = useState({ name: initialName, email: initialEmail });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!userId) return;

    setIsSubmitting(true);
    try {
      await adminApi.updateUser(userId, {
        name: editUserForm.name,
        email: editUserForm.email,
      });
      onSuccess();
      onClose();
    } catch (error) {
      console.error('Failed to update user:', error);
      alert('사용자 정보 수정에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="bg-[#051424] border-[rgba(65,71,81,0.3)] text-white sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="text-[#d4e4fa] text-lg font-semibold">사용자 정보 수정</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="editName" className="text-right text-[#a4c9ff] text-sm">
              이름
            </Label>
            <Input
              id="editName"
              value={editUserForm.name}
              onChange={(e) => setEditUserForm({ ...editUserForm, name: e.target.value })}
              className="col-span-3 bg-[#010f1f] border-[rgba(65,71,81,0.3)] focus-visible:ring-1 focus-visible:ring-white/20 text-[#d4e4fa]"
              placeholder="ex) 홍길동"
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="editEmail" className="text-right text-[#a4c9ff] text-sm">
              이메일
            </Label>
            <Input
              id="editEmail"
              type="email"
              value={editUserForm.email}
              onChange={(e) => setEditUserForm({ ...editUserForm, email: e.target.value })}
              className="col-span-3 bg-[#010f1f] border-[rgba(65,71,81,0.3)] focus-visible:ring-1 focus-visible:ring-white/20 text-[#d4e4fa]"
              placeholder="ex) hong@ssafy.com"
            />
          </div>
        </div>
        <DialogFooter>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-transparent hover:bg-white/5 border border-[rgba(65,71,81,0.3)] text-[#c1c7d3] rounded-md transition-colors text-sm font-medium"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="px-4 py-2 bg-[#3b82f6] hover:bg-[#2563eb] text-white rounded-md transition-colors text-sm font-medium disabled:opacity-50"
          >
            {isSubmitting ? '수정 중...' : '수정 완료'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
