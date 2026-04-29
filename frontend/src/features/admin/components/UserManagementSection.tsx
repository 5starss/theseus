import { useState, useEffect } from 'react';
import { Search, MoreVertical, Edit, Users, Settings2 } from 'lucide-react';
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
import { Input } from '../../../components/ui/input';

export default function UserManagementSection() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setIsLoading(true);
    try {
      const data = await adminApi.getUsers();
      setUsers(data);
    } catch (error) {
      console.error('Failed to fetch users:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredUsers = users.filter(user =>
    user.name.includes(searchTerm) ||
    user.employeeNumber.includes(searchTerm) ||
    (user.email && user.email.includes(searchTerm))
  );

  return (
    <div className="bg-[#0d1c2d] rounded-lg border border-[rgba(65,71,81,0.3)] shadow-2xl overflow-hidden flex flex-col h-full">
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
          <button className="flex items-center gap-2 bg-[#273647] hover:bg-[#34485e] transition-colors px-4 py-1.5 rounded h-8">
            <Settings2 className="w-3.5 h-3.5 text-[#60a5fa]" />
            <span className="text-[14px] font-medium text-[#60a5fa]">편집</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader className="bg-[rgba(28,43,60,0.5)] border-b border-[rgba(65,71,81,0.1)] sticky top-0 z-10">
            <TableRow className="border-none hover:bg-transparent">
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">사번</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">이름</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">아이디</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">이메일</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px] text-right">상태</TableHead>
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
                  <TableCell className="text-[#d4e4fa] px-6 py-[10px] text-[16px] font-medium">{user.name}</TableCell>
                  <TableCell className="text-[#c1c7d3] px-6 py-[10px] text-[16px]">{(user.email || '').split('@')[0] || '-'}</TableCell>
                  <TableCell className="text-[#c1c7d3] px-6 py-[10px] text-[16px]">{user.email || '-'}</TableCell>
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
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Footer / Pagination Placeholder */}
      <div className="h-[65px] px-4 border-t border-[rgba(65,71,81,0.1)] flex items-center justify-between shrink-0">
        <span className="text-xs text-white/40">Total {filteredUsers.length} users</span>
        <div className="flex items-center gap-1">
          {/* Pagination could go here */}
        </div>
      </div>
    </div>
  );
}
