import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface RenameSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (newTitle: string) => Promise<void>;
  initialTitle: string;
}

export function RenameSessionModal({
  isOpen,
  onClose,
  onConfirm,
  initialTitle,
}: RenameSessionModalProps) {
  const [tempTitle, setTempTitle] = useState(initialTitle);
  const [isRenaming, setIsRenaming] = useState(false);

  const handleConfirm = async () => {
    if (!tempTitle || !tempTitle.trim() || tempTitle.trim() === initialTitle) {
      onClose();
      return;
    }

    setIsRenaming(true);
    try {
      await onConfirm(tempTitle.trim());
    } finally {
      setIsRenaming(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
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
              if (e.key === 'Enter') handleConfirm();
            }}
            autoFocus
          />
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-100 hover:bg-white/5"
          >
            취소
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isRenaming || !tempTitle.trim() || tempTitle.trim() === initialTitle}
            className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold"
          >
            {isRenaming ? '저장 중...' : '저장'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
