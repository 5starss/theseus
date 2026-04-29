import { useState, useEffect } from 'react';
import { Search, MoreVertical, Edit, Users, Settings2, Trash2, UserPlus, ChevronLeft, ChevronRight } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import type { UserResponse } from '../../../api/admin';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../../components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../../components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../../components/ui/dialog';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';

export default function UserManagementSection() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isAddUserOpen, setIsAddUserOpen] = useState(false);
  const [newUserForm, setNewUserForm] = useState({
    employeeNumber: '',
    name: '',
    email: '',
    password: '',
  });

  // Pagination states
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [totalElements, setTotalElements] = useState(0);
  // Reset to page 0 when search term changes
  useEffect(() => {
    setPage(0);
  }, [searchTerm]);

  // Fetch users when page changes
  useEffect(() => {
    fetchUsers();
  }, [page]);

  const fetchUsers = async () => {
    setIsLoading(true);
    try {
      const data = await adminApi.getUsers(page, 8);
      if (data && data.content) {
        setUsers(data.content);
        setTotalPages(data.totalPages);
        setTotalElements(data.totalElements);
      } else {
        setUsers([]);
        setTotalPages(0);
        setTotalElements(0);
      }
    } catch (error) {
      console.error('Failed to fetch users:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddUser = async () => {
    try {
      await adminApi.createUser({
        employeeNumber: newUserForm.employeeNumber,
        name: newUserForm.name,
        email: newUserForm.email,
        password: newUserForm.password,
        systemRole: 'USER',
      });
      setIsAddUserOpen(false);
      setNewUserForm({ employeeNumber: '', name: '', email: '', password: '' });
      fetchUsers();
    } catch (error) {
      console.error('Failed to create user:', error);
      alert('사용자 생성에 실패했습니다.');
    }
  };

  const filteredUsers = users.filter(user =>
    user.name.includes(searchTerm) ||
    user.employeeNumber.includes(searchTerm) ||
    (user.email && user.email.includes(searchTerm))
  );

  return (
    <div className="bg-[#0d1c2d] rounded-lg border border-[rgba(65,71,81,0.3)] shadow-2xl overflow-hidden flex flex-col">
      <div className="px-6 pt-6 pb-[25px] border-b border-[rgba(65,71,81,0.2)] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded bg-[rgba(164,201,255,0.1)] flex items-center justify-center shrink-0">
            <Users className="w-5 h-5 text-[#a4c9ff]" />
          </div>
          <div className="flex flex-col">
            <h3 className="text-[18px] font-medium text-[#d4e4fa]">사용자 관리</h3>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#6b7280]" />
            <Input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="사용자 검색..."
              className="w-[192px] h-8 pl-9 bg-[#010f1f] border-[rgba(65,71,81,0.2)] text-[#6b7280] text-[12px] placeholder:text-[#6b7280] focus-visible:ring-1 focus-visible:ring-white/20 rounded"
            />
          </div>
          {isEditing && (
            <button
              onClick={() => setIsAddUserOpen(true)}
              className="flex items-center gap-2 bg-[#1a2c42] hover:bg-[#233852] border border-[#a4c9ff]/20 transition-colors px-4 py-1.5 rounded h-8"
            >
              <UserPlus className="w-3.5 h-3.5 text-[#a4c9ff]" />
              <span className="text-[14px] font-medium text-[#a4c9ff]">추가</span>
            </button>
          )}
          <button
            onClick={() => setIsEditing(!isEditing)}
            className={`flex items-center gap-2 transition-colors px-4 py-1.5 rounded h-8 ${isEditing ? 'bg-[#3b82f6] hover:bg-[#2563eb]' : 'bg-[#273647] hover:bg-[#34485e]'}`}
          >
            <Settings2 className={`w-3.5 h-3.5 ${isEditing ? 'text-white' : 'text-[#60a5fa]'}`} />
            <span className={`text-[14px] font-medium ${isEditing ? 'text-white' : 'text-[#60a5fa]'}`}>{isEditing ? '완료' : '편집'}</span>
          </button>
        </div>
      </div>

      <div className="w-full min-h-[500px]">
        <Table>
          <TableHeader className="bg-[rgba(28,43,60,0.5)] border-b border-[rgba(65,71,81,0.1)] sticky top-0 z-10">
            <TableRow className="border-none hover:bg-transparent">
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">사번</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">이름</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">아이디</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px] text-center">이메일</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px] text-center">상태</TableHead>
              <TableHead className="text-right text-white/60 font-medium h-10 px-6 py-2"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-white/40">
                  로딩 중...
                </TableCell>
              </TableRow>
            ) : filteredUsers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-white/40">
                  사용자가 없습니다.
                </TableCell>
              </TableRow>
            ) : (
              filteredUsers.map((user) => (
                <TableRow key={user.id} className="border-t border-[rgba(65,71,81,0.1)]">
                  <TableCell className="text-[#a4c9ff] px-6 py-[10px] text-[13px] font-mono">{user.employeeNumber}</TableCell>
                  <TableCell className="text-[#d4e4fa] px-6 py-[10px] text-[13px]">{user.name}</TableCell>
                  <TableCell className="text-[#c1c7d3] px-6 py-[10px] text-[13px]">{(user.email || '').split('@')[0] || '-'}</TableCell>
                  <TableCell className="text-[#c1c7d3] px-6 py-[10px] text-[13px]">{user.email || '-'}</TableCell>
                  <TableCell className="px-6 py-[10px] text-right">
                    {user.status === 'ACTIVE' ? (
                      <span className="inline-flex items-center justify-center px-[9px] py-[3px] rounded-[2px] bg-[rgba(34,197,94,0.1)] border border-[rgba(34,197,94,0.2)] text-[10px] font-bold text-[#4ade80] uppercase">
                        active
                      </span>
                    ) : (
                      <span className="inline-flex items-center justify-center px-[9px] py-[3px] rounded-[2px] bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.2)] text-[10px] font-bold text-[#f87171] uppercase">
                        offline
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="px-6 text-right py-3">
                    {isEditing ? (
                      <button className="p-2 hover:bg-red-500/10 rounded-md transition-colors text-red-400/60 hover:text-red-400">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    ) : (
                      <DropdownMenu>
                        <DropdownMenuTrigger className="p-2 hover:bg-white/10 rounded-md transition-colors outline-none text-white/60">
                          <MoreVertical className="w-4 h-4" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="bg-[#051424] border-white/10 text-white min-w-[150px]">
                          <DropdownMenuItem className="hover:bg-white/10 focus:bg-white/10 cursor-pointer gap-2">
                            <Edit className="w-4 h-4" />
                            <span>정보 수정</span>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Footer / Pagination */}
      <div className="h-[65px] px-4 border-t border-[rgba(65,71,81,0.1)] flex items-center justify-between shrink-0">
        <span className="text-xs text-white/40">Total {totalElements} users</span>
        <div className="flex items-center gap-1">
          <button
            disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
            className="px-2 py-1 text-xs text-white/60 hover:text-white disabled:opacity-50"
          >
            Prev
          </button>
          <span className="text-xs text-white/60 px-2">{page + 1} / {totalPages || 1}</span>
          <button
            disabled={page >= (totalPages || 1) - 1}
            onClick={() => setPage(p => p + 1)}
            className="px-2 py-1 text-xs text-white/60 hover:text-white disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>

      <Dialog open={isAddUserOpen} onOpenChange={setIsAddUserOpen}>
        <DialogContent className="bg-[#051424] border-[rgba(65,71,81,0.3)] text-white sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-[#d4e4fa] text-lg font-semibold">새 사용자 추가</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="employeeNumber" className="text-right text-[#a4c9ff] text-sm">
                사번
              </Label>
              <Input
                id="employeeNumber"
                value={newUserForm.employeeNumber}
                onChange={(e) => setNewUserForm({ ...newUserForm, employeeNumber: e.target.value })}
                className="col-span-3 bg-[#010f1f] border-[rgba(65,71,81,0.3)] focus-visible:ring-1 focus-visible:ring-white/20 text-[#d4e4fa]"
                placeholder="ex) 0000000"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="name" className="text-right text-[#a4c9ff] text-sm">
                이름
              </Label>
              <Input
                id="name"
                value={newUserForm.name}
                onChange={(e) => setNewUserForm({ ...newUserForm, name: e.target.value })}
                className="col-span-3 bg-[#010f1f] border-[rgba(65,71,81,0.3)] focus-visible:ring-1 focus-visible:ring-white/20 text-[#d4e4fa]"
                placeholder="ex) 홍길동"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="email" className="text-right text-[#a4c9ff] text-sm">
                이메일
              </Label>
              <Input
                id="email"
                type="email"
                value={newUserForm.email}
                onChange={(e) => setNewUserForm({ ...newUserForm, email: e.target.value })}
                className="col-span-3 bg-[#010f1f] border-[rgba(65,71,81,0.3)] focus-visible:ring-1 focus-visible:ring-white/20 text-[#d4e4fa]"
                placeholder="ex) hong@ssafy.com"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="password" className="text-right text-[#a4c9ff] text-sm">
                비밀번호
              </Label>
              <Input
                id="password"
                type="password"
                value={newUserForm.password}
                onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value })}
                className="col-span-3 bg-[#010f1f] border-[rgba(65,71,81,0.3)] focus-visible:ring-1 focus-visible:ring-white/20 text-[#d4e4fa]"
                placeholder="비밀번호를 입력하세요"
              />
            </div>
          </div>
          <DialogFooter>
            <button
              onClick={() => setIsAddUserOpen(false)}
              className="px-4 py-2 bg-transparent hover:bg-white/5 border border-[rgba(65,71,81,0.3)] text-[#c1c7d3] rounded-md transition-colors text-sm font-medium"
            >
              취소
            </button>
            <button
              onClick={handleAddUser}
              className="px-4 py-2 bg-[#3b82f6] hover:bg-[#2563eb] text-white rounded-md transition-colors text-sm font-medium"
            >
              사용자 추가
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
