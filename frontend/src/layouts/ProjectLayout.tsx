import { Outlet, useParams } from 'react-router-dom';
import { Sidebar } from '@/features/projects/components/Sidebar';

export default function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>();

  // TODO: Validate projectId or fetch basic project info if needed at layout level

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
