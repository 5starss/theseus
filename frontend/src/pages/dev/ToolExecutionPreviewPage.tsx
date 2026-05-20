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
          content: 'bash와 glob Tool 실행 상태 카드가 어떻게 접히고 최종 상태로 정리되는지 확인해줘.',
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
      toolName: 'bash',
      toolUseId: 'dev-preview-bash',
      toolInput: {
        command: 'npm run build',
      },
      status: 'started',
    });
    upsertToolExecutionNotice({
      noticeType: 'TOOL_EXECUTION_STARTED',
      toolName: 'glob',
      toolUseId: 'dev-preview-glob',
      toolInput: {
        pattern: 'frontend/src/**/*.tsx',
      },
      status: 'started',
    });

    const timer = window.setTimeout(() => {
      upsertToolExecutionNotice({
        noticeType: 'TOOL_EXECUTION_FAILED',
        toolName: 'bash',
        toolUseId: null,
        toolInput: {
          command: 'npm run build',
        },
        output: 'Build failed with a demonstration error.',
        isError: true,
        status: 'failed',
      });
      upsertToolExecutionNotice({
        noticeType: 'TOOL_EXECUTION_COMPLETED',
        toolName: 'glob',
        toolUseId: null,
        toolInput: {
          pattern: 'frontend/src/**/*.tsx',
        },
        output: '12 files matched.',
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
