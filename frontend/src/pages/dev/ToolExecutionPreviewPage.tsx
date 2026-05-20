import { useEffect } from 'react';
import { ChatDashboard } from '@/features/projects/components/chat/ChatDashboard';
import { useChatSessionStore } from '@/features/projects/stores/useChatSessionStore';
import { useProjectStore } from '@/features/projects/stores/useProjectStore';
import { ToolPlanMode } from '@/features/projects/types/chat';

export default function ToolExecutionPreviewPage() {
  const initSession = useChatSessionStore((state) => state.initSession);
  const setMode = useChatSessionStore((state) => state.setMode);
  const setIsGenerating = useChatSessionStore((state) => state.setIsGenerating);
  const setProgressInfo = useChatSessionStore((state) => state.setProgressInfo);
  const upsertToolExecutionNotice = useChatSessionStore((state) => state.upsertToolExecutionNotice);
  const setProject = useProjectStore((state) => state.setProject);

  useEffect(() => {
    const now = new Date().toISOString();
    const toolUseId = 'dev-preview-remote-grep';

    setProject({
      projectMemberId: 1,
      projectId: 1,
      projectName: 'Tool execution preview',
      userId: 1,
      employeeNumber: 'DEV-001',
      name: 'Dev User',
      projectRole: 'ADMIN',
      accessLevel: 3,
      canCreateTool: true,
      canUseTool: true,
      canUpdateTool: true,
      canDeleteTool: true,
      status: 'IN_PROGRESS',
      isProjectAdminUser: true,
      createdByUserId: null,
      createdAt: now,
      updatedAt: now,
    });

    initSession({
      messages: [
        {
          messageId: 'dev-tool-preview-user',
          senderType: 'USER',
          messageType: 'CHAT',
          contentType: 'TEXT',
          content: 'remote_grep으로 Tool 실행 상태 카드가 어떻게 보이는지 확인해줘.',
          createdAt: now,
        },
      ],
      plan: null,
      phase: null,
      toolId: null,
      toolPlanGroupId: null,
      toolPlanId: null,
      runId: null,
      planStatus: null,
      createdTool: null,
      toolResult: null,
      title: 'Tool execution card preview',
      isClosed: false,
      planVersion: 0,
      draftVersion: 0,
    });

    setMode(ToolPlanMode.AGENT);
    setIsGenerating(true);
    setProgressInfo({
      step: 'AGENT Processing',
      message: '도구 호출을 실행하는 중입니다.',
      percent: 35,
    });

    upsertToolExecutionNotice({
      noticeType: 'TOOL_EXECUTION_STARTED',
      toolName: 'remote_grep',
      toolUseId,
      toolInput: {
        query: 'TOOL_EXECUTION',
        path: 'frontend/src/features/projects',
      },
      status: 'started',
    });

    const timer = window.setTimeout(() => {
      upsertToolExecutionNotice({
        noticeType: 'TOOL_EXECUTION_COMPLETED',
        toolName: 'remote_grep',
        toolUseId,
        toolInput: {
          query: 'TOOL_EXECUTION',
          path: 'frontend/src/features/projects',
        },
        output: '3 matches found in ChatArea.tsx, MessageItem.tsx, and useChatStreamSSE.ts.',
        isError: false,
        status: 'completed',
      });
      setProgressInfo(null);
      setIsGenerating(false);
    }, 1800);

    return () => {
      window.clearTimeout(timer);
    };
  }, [initSession, setIsGenerating, setMode, setProgressInfo, setProject, upsertToolExecutionNotice]);

  return (
    <div className="h-screen bg-[#051424]">
      <ChatDashboard />
    </div>
  );
}
