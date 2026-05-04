import { useParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { ProjectGeneralSettings } from '@/features/projects/components/settings/ProjectGeneralSettings';
import { ProjectMemberManagement } from '@/features/projects/components/settings/ProjectMemberManagement';
import { ToolApprovalManagement } from '@/features/projects/components/settings/ToolApprovalManagement';

export default function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>();

  if (!projectId) {
    return null;
  }

  return (
    <div className="flex-1 w-full h-full p-8 overflow-y-auto relative">
      {/* Background Grid Effect */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:40px_40px] opacity-10 pointer-events-none" />

      <div className="max-w-6xl mx-auto space-y-8 relative z-10">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-1.5 h-6 bg-blue-400 rounded-full" />
            <h1 className="text-3xl font-['Space_Grotesk'] font-bold tracking-tight text-white">프로젝트 설정</h1>
          </div>
          <p className="text-sm text-slate-400 font-medium">
            프로젝트 정보 수정, 멤버 관리, 도구 승인 요청을 처리할 수 있습니다.
          </p>
        </div>

        <Tabs defaultValue="general" className="w-full">
          <TabsList className="bg-slate-900/50 backdrop-blur border border-slate-800 p-1 mb-8">
            <TabsTrigger value="general" className="data-[state=active]:bg-blue-400 data-[state=active]:text-[#003a6b]">일반 설정</TabsTrigger>
            <TabsTrigger value="members" className="data-[state=active]:bg-blue-400 data-[state=active]:text-[#003a6b]">멤버 관리</TabsTrigger>
            <TabsTrigger value="approvals" className="data-[state=active]:bg-blue-400 data-[state=active]:text-[#003a6b]">도구 승인 대기열</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="mt-0 focus-visible:outline-none">
            <ProjectGeneralSettings projectId={projectId} />
          </TabsContent>

          <TabsContent value="members" className="mt-0 focus-visible:outline-none">
            <ProjectMemberManagement projectId={projectId} />
          </TabsContent>

          <TabsContent value="approvals" className="mt-0 focus-visible:outline-none">
            <ToolApprovalManagement projectId={projectId} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
