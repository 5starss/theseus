import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { toolApi } from '../api';
import type { ToolItem } from '../types';
import { ToolCard } from './ToolCard';
import { Activity, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ToolDetailModal } from './ToolDetailModal';
import { useProjectStore } from '@/features/projects/stores/useProjectStore';

const ITEMS_PER_PAGE = 9;

export function ToolList() {
  const { projectId } = useParams<{ projectId: string }>();
  const [tools, setTools] = useState<ToolItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedTool, setSelectedTool] = useState<ToolItem | null>(null);
  const [fetchTrigger, setFetchTrigger] = useState(0);
  const [updatingToolId, setUpdatingToolId] = useState<number | null>(null);
  const currentProject = useProjectStore((state) => state.currentProject);
  const canEditAccessLevel = currentProject?.projectRole === 'ADMIN';

  useEffect(() => {
    let isMounted = true;

    const fetchTools = async () => {
      if (!projectId) return;

      setIsLoading(true);
      try {
        const data = await toolApi.getTools(projectId);
        if (isMounted) {
          setTools(data);
          setCurrentPage(1); // 데이터 로드 시 첫 페이지로 리셋
        }
      } catch (error) {
        console.error('Failed to load tools:', error);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchTools();

    return () => {
      isMounted = false;
    };
  }, [projectId, fetchTrigger]);

  const handleToolClick = (tool: ToolItem) => {
    setSelectedTool(tool);
  };

  const handleAccessLevelChange = async (tool: ToolItem, accessLevel: number) => {
    if (!projectId || tool.toolGrade === accessLevel) return;

    setUpdatingToolId(tool.toolId);
    try {
      const updatedTool = await toolApi.updateToolAccessLevel(projectId, tool.toolId, accessLevel);
      setTools((prevTools) =>
        prevTools.map((item) => (item.toolId === updatedTool.toolId ? { ...item, ...updatedTool } : item))
      );
      setSelectedTool((prevTool) =>
        prevTool?.toolId === updatedTool.toolId ? { ...prevTool, ...updatedTool } : prevTool
      );
      alert('Tool access level 수정이 완료되었습니다.');
    } catch (error) {
      console.error('Failed to update tool access level:', error);
      alert('Tool access level 수정에 실패했습니다.');
    } finally {
      setUpdatingToolId(null);
    }
  };

  // 페이징 계산
  const totalPages = Math.ceil(tools.length / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const currentTools = tools.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  return (
    <>
      <div className="relative w-full h-full min-h-[calc(100vh-4rem)] bg-slate-950 flex justify-center overflow-x-hidden">
        {/* Ambient Background Glow */}
        <div className="absolute top-0 left-1/4 right-1/4 h-96 bg-blue-500/5 blur-[80px] rounded-full pointer-events-none" />

        <div className="relative w-full max-w-[1152px] px-6 pt-8 pb-24 flex flex-col">
          {/* Content Area */}
          <div className="flex-1 flex flex-col gap-8">
            {/* Page Header */}
            <div className="flex flex-col gap-3">
              <h1 className="text-3xl font-bold text-slate-100 pt-5">
                도구 목록
              </h1>
            </div>

            {/* Tool Grid */}
            {isLoading ? (
              <div className="flex-1 flex items-center justify-center py-20 text-slate-500">
                <Activity className="w-6 h-6 animate-spin mr-2" />
                도구 목록을 불러오는 중...
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {currentTools.map((tool) => (
                  <ToolCard
                    key={tool.toolId}
                    tool={tool}
                    onClick={() => handleToolClick(tool)}
                    canEditAccessLevel={canEditAccessLevel}
                    isUpdatingAccessLevel={updatingToolId === tool.toolId}
                    onAccessLevelChange={(accessLevel) => handleAccessLevelChange(tool, accessLevel)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Pagination Controls - Pushed to bottom */}
          {!isLoading && totalPages > 1 && (
            <div className="mt-5 flex items-center justify-center gap-4 border-t border-slate-900 pt-8">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 transition-all"
              >
                <ChevronLeft className="w-4 h-4 mr-2" />
                이전
              </Button>

              <div className="flex items-center gap-2">
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`w-8 h-8 rounded-md text-sm font-medium transition-all ${currentPage === pageNum
                      ? 'bg-blue-600 text-white shadow-[0_0_15px_rgba(37,99,235,0.4)]'
                      : 'text-slate-500 hover:text-slate-200 hover:bg-slate-800'
                      }`}
                  >
                    {pageNum}
                  </button>
                ))}
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 transition-all"
              >
                다음
                <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          )}
        </div>
      </div>
      
      {selectedTool && projectId && (
        <ToolDetailModal
          projectId={projectId}
          toolItem={selectedTool}
          onClose={() => setSelectedTool(null)}
          onDeleteSuccess={() => setFetchTrigger(prev => prev + 1)}
        />
      )}
    </>
  );
}

