import { useParams, useSearchParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { ProjectGeneralSettings } from '@/features/projects/components/settings/ProjectGeneralSettings';
import { ProjectMemberManagement } from '@/features/projects/components/settings/ProjectMemberManagement';
import { RemoteWorkspaceManagement } from '@/features/projects/components/settings/RemoteWorkspaceManagement';
import { ToolApprovalManagement } from '@/features/projects/components/settings/ToolApprovalManagement';
import { ToolUsageHistoryTab } from '@/features/projects/components/settings/ToolUsageHistoryTab';

export default function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'general';

  const handleTabChange = (value: string) => {
    setSearchParams({ tab: value });
  };

  if (!projectId) {
    return null;
  }

  return (
    <div className="flex-1 w-full h-full p-8 overflow-y-auto relative">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:40px_40px] opacity-10 pointer-events-none" />

      <div className="max-w-6xl mx-auto space-y-8 relative z-10">
        <div className="min-w-max">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-1.5 h-6 bg-blue-400 rounded-full" />
            <h1 className="text-3xl font-['Space_Grotesk'] font-bold tracking-tight text-white whitespace-nowrap">프로젝트 설정</h1>
          </div>
          <p className="text-sm text-slate-400 font-medium whitespace-nowrap">
            프로젝트 정보, 멤버, ToolPlan 승인 요청, Remote Workspace를 관리합니다.
          </p>
        </div>

        <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
          <TabsList className="bg-slate-900/50 backdrop-blur border border-slate-800 p-1 mb-8">
            <TabsTrigger value="general" className="data-[state=active]:bg-blue-400 data-[state=active]:text-[#003a6b]">일반 설정</TabsTrigger>
            <TabsTrigger value="members" className="data-[state=active]:bg-blue-400 data-[state=active]:text-[#003a6b]">멤버 관리</TabsTrigger>
            <TabsTrigger value="tool-usages" className="data-[state=active]:bg-blue-400 data-[state=active]:text-[#003a6b]">도구 사용 목록</TabsTrigger>
            <TabsTrigger value="approvals" className="data-[state=active]:bg-blue-400 data-[state=active]:text-[#003a6b]">ToolPlan 승인</TabsTrigger>
            <TabsTrigger value="remote-workspaces" className="data-[state=active]:bg-blue-400 data-[state=active]:text-[#003a6b]">Remote Workspace</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="mt-0 focus-visible:outline-none">
            <ProjectGeneralSettings projectId={projectId} />
          </TabsContent>

          <TabsContent value="members" className="mt-0 focus-visible:outline-none">
            <ProjectMemberManagement projectId={projectId} />
          </TabsContent>

          <TabsContent value="tool-usages" className="mt-0 focus-visible:outline-none">
            <ToolUsageHistoryTab projectId={projectId} />
          </TabsContent>

          <TabsContent value="approvals" className="mt-0 focus-visible:outline-none">
            <ToolApprovalManagement projectId={projectId} />
          </TabsContent>

          <TabsContent value="remote-workspaces" className="mt-0 focus-visible:outline-none">
            <RemoteWorkspaceManagement projectId={projectId} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
