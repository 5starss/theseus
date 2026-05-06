import { Outlet, useParams } from 'react-router-dom';
import { Sidebar } from '@/features/projects/components/Sidebar';
import { useEffect } from 'react';
import { projectApi } from '@/features/projects/api';
import { useProjectStore } from '@/features/projects/stores/useProjectStore';

export default function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const setProject = useProjectStore((state) => state.setProject);
  const setError = useProjectStore((state) => state.setError);
  const setIsLoading = useProjectStore((state) => state.setIsLoading);
  const reset = useProjectStore((state) => state.reset);

  useEffect(() => {
    let cancelled = false;
    const fetchProjectInfo = async () => {
      if (!projectId) return;
      
      setIsLoading(true);
      try {
        const data = await projectApi.getProjectMe(projectId);
        if (cancelled) return;
        setProject(data);
      } catch (err: unknown) {
        if (!cancelled) {
          console.error('Failed to fetch project info:', err);
          const axiosErr = err as { response?: { data?: { message?: string } }; message?: string };
          setError(axiosErr.response?.data?.message || axiosErr.message || '프로젝트 정보를 불러오는데 실패했습니다.');
        }
      }
    };

    fetchProjectInfo();
    return () => {
      cancelled = true;
      reset();
    };
  }, [projectId, setProject, setError, setIsLoading, reset]);

  return (
    <div className="min-h-screen bg-[#010f1f] text-foreground flex relative overflow-hidden">
      {/* Global Left Sidebar */}
      <Sidebar projectId={projectId} />

      {/* Main Content Area */}
      <main className="flex-1 overflow-auto relative z-10 flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
