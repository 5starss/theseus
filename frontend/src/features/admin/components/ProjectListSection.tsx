import { useState, useEffect } from 'react';
import { Search, MoreVertical, Edit, Layers, Settings2, Plus, Trash2 } from 'lucide-react';
import { adminApi } from '../api';
import type { ProjectSummaryResponse } from '../api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { StatusBadge } from '@/components/StatusBadge';
import { Pagination } from '@/components/Pagination';
import AddProjectModal from './AddProjectModal';
import EditProjectModal from './EditProjectModal';

export default function ProjectListSection() {
  const [projects, setProjects] = useState<ProjectSummaryResponse[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<ProjectSummaryResponse | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [totalElements, setTotalElements] = useState(0);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  const refetch = () => setFetchTrigger(n => n + 1);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      try {
        const data = await adminApi.getProjects(page, 8);
        if (cancelled) return;
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
        if (!cancelled) {
          console.error('Failed to fetch projects:', error);
          setProjects([]);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [page, fetchTrigger]);

  const handleStatusToggle = async (projectId: number, currentStatus: 'ACTIVE' | 'INACTIVE') => {
    const newStatus = currentStatus === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    try {
      await adminApi.updateProject(projectId, { status: newStatus });
      refetch();
    } catch (error) {
      console.error('Failed to update project status:', error);
      alert('프로젝트 상태 변경에 실패했습니다.');
    }
  };

  const filteredProjects = projects.filter(project => {
    const searchLower = searchTerm.toLowerCase();
    return (
      project.name.toLowerCase().includes(searchLower) ||
      project.projectAdminName.toLowerCase().includes(searchLower) ||
      project.projectAdminEmployeeNumber.includes(searchTerm)
    );
  });

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
              onChange={(e) => { setSearchTerm(e.target.value); setPage(0); }}
              placeholder="프로젝트 검색..."
              className="w-[192px] h-8 pl-9 bg-[#010f1f] border-[rgba(65,71,81,0.2)] text-[#6b7280] text-[12px] placeholder:text-[#6b7280] focus-visible:ring-1 focus-visible:ring-white/20 rounded"
            />
          </div>
          {isEditing && (
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="flex items-center gap-2 bg-[#1a2c42] hover:bg-[#233852] border border-[#a4c9ff]/20 transition-colors px-4 py-1.5 rounded h-8"
            >
              <Plus className="w-3.5 h-3.5 text-[#a4c9ff]" />
              <span className="text-[14px] font-medium text-[#a4c9ff]">추가</span>
            </button>
          )}
          <button
            onClick={() => setIsEditing(!isEditing)}
            className={`flex items-center gap-2 transition-colors px-4 py-1.5 rounded h-8 ${isEditing ? 'bg-[#fabd34] hover:bg-[#e5ac2d]' : 'bg-[#273647] hover:bg-[#34485e]'}`}
          >
            <Settings2 className={`w-3.5 h-3.5 ${isEditing ? 'text-[#003a6b]' : 'text-[#fabd34]'}`} />
            <span className={`text-[14px] font-medium ${isEditing ? 'text-[#003a6b]' : 'text-[#fabd34]'}`}>{isEditing ? '완료' : '편집'}</span>
          </button>
        </div>
      </div>

      <div className="w-full min-h-[500px]">
        <Table className="table-fixed">
          <TableHeader className="bg-[rgba(28,43,60,0.5)] border-b border-[rgba(65,71,81,0.1)] sticky top-0 z-10">
            <TableRow className="border-none hover:bg-transparent">
              <TableHead className="text-[#c1c7d3] font-medium text-[14px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px] w-[180px]">프로젝트 명</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[14px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px] w-[140px]">담당자 사번</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[14px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px] w-[150px]">담당자 이름</TableHead>
              <TableHead className="text-[#c1c7d3] font-medium text-[14px] tracking-[1.2px] uppercase h-[40px] px-6 py-[10px] text-center w-[80px]">상태</TableHead>
              <TableHead className="text-right text-white/60 font-medium h-10 px-6 py-2 w-[83px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredProjects.length === 0 ? (
              !isLoading && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-white/40">
                    프로젝트가 없습니다.
                  </TableCell>
                </TableRow>
              )
            ) : (
              filteredProjects.map((project) => (
                <TableRow key={project.projectId} className="border-t border-[rgba(65,71,81,0.1)] h-[57px]">
                  <TableCell className="text-[#d4e4fa] px-6 py-[10px] text-[14px] font-medium truncate whitespace-nowrap">{project.name}</TableCell>
                  <TableCell className="text-[#a4c9ff] px-6 py-[10px] text-[15px] font-mono truncate whitespace-nowrap">{project.projectAdminEmployeeNumber}</TableCell>
                  <TableCell className="text-[#c1c7d3] px-6 py-[10px] text-[15px] font-medium truncate whitespace-nowrap">{project.projectAdminName}</TableCell>
                  <TableCell className="px-6 py-[10px] text-center">
                    <StatusBadge status={project.status} />
                  </TableCell>
                  <TableCell className="px-6 text-center py-3">
                    {isEditing && (
                      <div className="flex items-center justify-center gap-1">
                        <DropdownMenu>
                          <DropdownMenuTrigger className="p-2 hover:bg-white/10 rounded-md transition-colors outline-none text-white/60">
                            <MoreVertical className="w-4 h-4" />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="bg-[#051424] border-white/10 text-white min-w-[150px]">
                            <DropdownMenuItem
                              className="hover:bg-white/10 focus:bg-white/10 cursor-pointer gap-2"
                              onClick={() => {
                                setSelectedProject(project);
                                setIsEditModalOpen(true);
                              }}
                            >
                              <Edit className="w-4 h-4" />
                              <span>프로젝트 수정</span>
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <button
                          onClick={() => handleStatusToggle(project.projectId, project.status)}
                          className="p-2 hover:bg-red-500/10 rounded-md transition-colors text-red-400/60 hover:text-red-400"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
            {!isLoading && filteredProjects.length > 0 && filteredProjects.length < 8 && (
              Array.from({ length: 8 - filteredProjects.length }).map((_, index) => (
                <TableRow key={`empty-${index}`} className="border-t border-[rgba(65,71,81,0.05)] h-[57px] hover:bg-transparent">
                  <TableCell colSpan={5} />
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Footer / Pagination */}
      <Pagination
        page={page}
        totalPages={totalPages}
        totalElements={totalElements}
        onPageChange={setPage}
        itemName="projects"
      />

      <AddProjectModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={refetch}
      />

      <EditProjectModal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setSelectedProject(null);
        }}
        onSuccess={refetch}
        project={selectedProject}
        key={selectedProject?.projectId ?? 0}
      />
    </div>
  );
}
