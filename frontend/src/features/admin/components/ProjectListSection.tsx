import { useState, useEffect } from 'react';
import { Search, MoreVertical, Edit, Layers, Settings2 } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import type { ProjectSummaryResponse } from '../../../api/admin';
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

export default function ProjectListSection() {
  const [projects, setProjects] = useState<ProjectSummaryResponse[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [totalElements, setTotalElements] = useState(0);
  useEffect(() => {
    fetchProjects(page);
  }, [page]);

  const fetchProjects = async (pageNumber: number) => {
    setIsLoading(true);
    try {
      const data = await adminApi.getProjects(pageNumber, 8);
      if (data && data.content) {
        setProjects(data.content);
        setTotalPages(data.totalPages);
        setTotalElements(data.totalElements);
      } else {
        setProjects([]);
        setTotalPages(0);
        setTotalElements(0);
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error);
      setProjects([]);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredProjects = projects.filter(project =>
    project.name.includes(searchTerm) ||
    project.projectAdminName.includes(searchTerm) ||
    project.projectAdminEmployeeNumber.includes(searchTerm)
  );

  return (
    <div className="bg-[#0d1c2d] rounded-lg border border-[rgba(65,71,81,0.3)] shadow-2xl flex flex-col">
      <div className="px-6 pt-6 pb-[25px] border-b border-[rgba(65,71,81,0.2)] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded bg-[rgba(250,189,52,0.1)] flex items-center justify-center shrink-0">
            <Layers className="w-5 h-5 text-[#fabd34]" />
          </div>
          <div className="flex flex-col">
            <h3 className="text-[18px] font-medium text-[#d4e4fa]">프로젝트 목록</h3>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#6b7280]" />
            <Input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="프로젝트 검색..."
              className="w-[192px] h-8 pl-9 bg-[#010f1f] border-[rgba(65,71,81,0.2)] text-[#6b7280] text-[12px] placeholder:text-[#6b7280] focus-visible:ring-1 focus-visible:ring-white/20 rounded"
            />
          </div>
          <button className="flex items-center gap-2 bg-[#273647] hover:bg-[#34485e] transition-colors px-4 py-1.5 rounded h-8">
            <Settings2 className="w-3.5 h-3.5 text-[#fabd34]" />
            <span className="text-[14px] font-medium text-[#fabd34]">편집</span>
          </button>
        </div>
      </div>

      <div className="w-full min-h-[500px]">
        <Table>
          <TableHeader className="bg-[rgba(28,43,60,0.5)] border-b border-[rgba(65,71,81,0.1)] sticky top-0 z-10">
            <TableRow className="border-none hover:bg-transparent">
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">프로젝트 명</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">담당자 사번</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">담당자 이름</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[12px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px]">이메일</TableHead>
              <TableHead className="text-right text-white/60 font-medium h-10 px-6 py-2"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-white/40">
                  로딩 중...
                </TableCell>
              </TableRow>
            ) : filteredProjects.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-white/40">
                  프로젝트가 없습니다.
                </TableCell>
              </TableRow>
            ) : (
              filteredProjects.map((project) => (
                <TableRow key={project.projectId} className="border-t border-[rgba(65,71,81,0.1)]">
                  <TableCell className="text-[#d4e4fa] px-6 py-[10px] text-[16px] font-medium">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${project.status === 'ACTIVE' ? 'bg-[#60a5fa]' : 'bg-[#bcc7de]'}`} />
                      {project.name}
                    </div>
                  </TableCell>
                  <TableCell className="text-[#a4c9ff] px-6 py-[10px] text-[13px] font-mono">{project.projectAdminEmployeeNumber}</TableCell>
                  <TableCell className="text-[#c1c7d3] px-6 py-[10px] text-[16px] font-medium">{project.projectAdminName}</TableCell>
                  <TableCell className="text-[#c1c7d3] px-6 py-[10px] text-[16px]">{project.projectAdminEmployeeNumber.toLowerCase()}@theseus.ai</TableCell>
                  <TableCell className="px-6 text-right py-3">
                    <DropdownMenu>
                      <DropdownMenuTrigger className="p-2 hover:bg-white/10 rounded-md transition-colors outline-none text-white/60">
                        <MoreVertical className="w-4 h-4" />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="bg-[#051424] border-white/10 text-white min-w-[150px]">
                        <DropdownMenuItem className="hover:bg-white/10 focus:bg-white/10 cursor-pointer gap-2">
                          <Edit className="w-4 h-4" />
                          <span>프로젝트 수정</span>
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
        <span className="text-xs text-white/40">Total {totalElements} projects</span>
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
    </div>
  );
}
