import { useState } from 'react';
import { adminApi } from '../api';
import type { UserResponse } from '../api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface AddProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function AddProjectModal({ isOpen, onClose, onSuccess }: AddProjectModalProps) {
  const [projectName, setProjectName] = useState('');
  const [description, setDescription] = useState('');
  const [employeeNumber, setEmployeeNumber] = useState('');
  const [searchedUser, setSearchedUser] = useState<UserResponse | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const handleSearch = async () => {
    const trimmedId = employeeNumber.trim();
    if (!trimmedId) return;

    setIsSearching(true);
    try {
      console.log('Searching for employeeNumber:', trimmedId);
      const user = await adminApi.searchUserByEmployeeNumber(trimmedId);
      if (user) {
        setSearchedUser(user);
      } else {
        alert('사용자를 찾을 수 없습니다.');
        setSearchedUser(null);
      }
    } catch (error: unknown) {
      console.error('Search failed:', error);
      const axiosErr = error as { response?: { data?: { message?: string } } };
      const message = axiosErr.response?.data?.message || '사용자를 찾을 수 없습니다.';
      alert(message);
      setSearchedUser(null);
    } finally {
      setIsSearching(false);
    }
  };

  const handleCreate = async () => {
    if (!projectName || !searchedUser) return;
    setIsCreating(true);
    try {
      await adminApi.createProject({
        name: projectName,
        description: description,
        adminEmployeeNumber: searchedUser.employeeNumber,
        adminName: searchedUser.name,
      });
      setProjectName('');
      setDescription('');
      setEmployeeNumber('');
      setSearchedUser(null);
      onSuccess();
      onClose();
    } catch (error) {
      console.error('Failed to create project:', error);
      alert('프로젝트 생성에 실패했습니다.');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="bg-[#1c2b3c] border-[#1f2937] text-white sm:max-w-[448px] p-0 overflow-hidden shadow-[0px_20px_50px_0px_rgba(0,0,0,0.5)] rounded-[8px]">
        <DialogHeader className="px-8 pt-8 pb-6 border-b border-[rgba(65,71,81,0.3)]">
          <DialogTitle className="font-['WenQuanYi_Zen_Hei:Medium',sans-serif] text-[20px] text-white tracking-[-0.5px]">새 프로젝트 생성</DialogTitle>
        </DialogHeader>

        <div className="px-8 py-6 flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <Label className="font-['WenQuanYi_Zen_Hei:Medium',sans-serif] text-[#c1c7d3] text-[12px] tracking-[0.6px] uppercase">프로젝트 명</Label>
            <Input
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="프로젝트 명 입력"
              className="bg-[#010f1f] border-[#414751] text-[#d4e4fa] h-[48px] px-[17px] text-[14px]"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label className="font-['WenQuanYi_Zen_Hei:Medium',sans-serif] text-[#c1c7d3] text-[12px] tracking-[0.6px] uppercase">프로젝트 설명</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="프로젝트 설명 입력"
              className="bg-[#010f1f] border-[#414751] text-[#d4e4fa] h-[48px] px-[17px] text-[14px]"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label className="font-['WenQuanYi_Zen_Hei:Medium',sans-serif] text-[#c1c7d3] text-[12px] tracking-[0.6px] uppercase">담당자 사번</Label>
            <div className="relative flex items-center">
              <Input
                value={employeeNumber}
                onChange={(e) => {
                  setEmployeeNumber(e.target.value);
                  setSearchedUser(null);
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="담당자 사번 입력"
                className="bg-[#010f1f] border-[#414751] text-[#d4e4fa] h-[48px] px-[17px] pr-[60px] text-[14px] w-full focus-visible:ring-1 focus-visible:ring-white/20"
              />
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleSearch();
                }}
                disabled={isSearching || !employeeNumber.trim()}
                className="absolute right-3 h-8 px-2 flex items-center justify-center text-[#60a5fa] text-[12px] hover:text-white disabled:opacity-50 font-medium z-10 transition-colors"
              >
                {isSearching ? "..." : "검색"}
              </button>
            </div>
          </div>

          {searchedUser && (
            <div className="bg-[#0d1c2d] border border-[rgba(96,165,250,0.2)] rounded-[4px] p-[17px] flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="font-['WenQuanYi_Zen_Hei:Medium',sans-serif] text-[14px] text-white">{searchedUser.name}</span>
                <div className="bg-[rgba(96,165,250,0.1)] px-1.5 py-0.5 rounded-[2px]">
                  <span className="text-[#60a5fa] text-[10px] font-['Inter:Regular',sans-serif]">ID: {searchedUser.employeeNumber}</span>
                </div>
              </div>
              <span className="text-[#c1c7d3] text-[12px] font-['Inter:Regular',sans-serif]">{searchedUser.email}</span>
            </div>
          )}
        </div>

        <DialogFooter className="px-8 pb-8 pt-2 sm:justify-end gap-3">
          <button
            onClick={onClose}
            className="border border-[#414751] rounded-[4px] px-[25px] py-[11px] font-['WenQuanYi_Zen_Hei:Medium',sans-serif] text-[#c1c7d3] text-[14px] hover:bg-white/5 transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleCreate}
            disabled={!projectName || !searchedUser || isCreating}
            className="bg-[#3b82f6] rounded-[4px] px-[24px] py-[10px] font-['WenQuanYi_Zen_Hei:Medium',sans-serif] text-white text-[14px] font-medium hover:bg-[#2563eb] transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-[0px_10px_15px_-3px_rgba(59,130,246,0.2)]"
          >
            {isCreating ? '생성 중...' : '생성하기'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
