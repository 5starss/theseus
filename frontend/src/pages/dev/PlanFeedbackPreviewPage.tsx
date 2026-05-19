import { useEffect } from 'react';
import { ChatDashboard } from '@/features/projects/components/chat/ChatDashboard';
import { useChatSessionStore } from '@/features/projects/stores/useChatSessionStore';
import { useProjectStore } from '@/features/projects/stores/useProjectStore';
import type { StructuredPlan } from '@/features/projects/types/chat';

const previewPlan: StructuredPlan = {
  version: 'dev-preview',
  blocks: [
    {
      blockId: 'task-1',
      title: 'System Health Reporter 도구 구현',
      content: '',
      tier: 'T1',
      status: 'WAIT_FOR_REVIEW',
      fields: [
        {
          fieldId: 'problem',
          label: 'Problem',
          value: '지표 모니터링, 조건부 심층 분석, 통합 리포트 생성을 한 번에 수행하는 단일 인터페이스가 필요함.',
          feedbackTarget: 'task-1.problem',
        },
        {
          fieldId: 'solution',
          label: 'Solution',
          value: '기존 `cpu_monitor` 및 `ram_advanced_monitor`를 `context.call_tool`로 호출하여 데이터를 취합하고, 임계치 기반 로직을 포함한 Python 클래스로 구현.',
          feedbackTarget: 'task-1.solution',
        },
        {
          fieldId: 'expected_effect',
          label: 'Expected effect',
          value: '시스템 부하 발생 시 즉각적인 원인 파악 가능 및 운영 효율성 증대',
          feedbackTarget: 'task-1.expected_effect',
        },
        {
          fieldId: 'target_files',
          label: 'Target files',
          value: [
            '/backend/theseus-core-server/theseus_engine/custom_tools/projects/4/system_health_reporter_tool.py',
            '/backend/theseus-core-server/theseus_engine/custom_tools/projects/4/system_health_reporter_tool.meta.json',
          ].join('\n'),
          feedbackTarget: 'task-1.target_files',
        },
      ],
    },
    {
      blockId: 'task-2',
      title: '심층 분석 로직 설계',
      content: '',
      parentId: 'task-1',
      tier: 'T2',
      status: 'WAIT_FOR_REVIEW',
      fields: [
        {
          fieldId: 'description',
          label: 'Description',
          value: 'CPU/RAM 수집 결과를 정규화하고, 임계치 초과 시 병목 후보와 완화 제안을 구성합니다.',
          feedbackTarget: 'task-2.description',
        },
        {
          fieldId: 'integration_points',
          label: 'Integration points',
          value: '`context.call_tool("cpu_monitor")`, `context.call_tool("ram_advanced_monitor")`',
          feedbackTarget: 'task-2.integration_points',
        },
        {
          fieldId: 'sequential_dependencies',
          label: 'Sequential dependencies',
          value: 'task-1의 도구 파일 구조와 메타데이터 정의가 먼저 확정되어야 함.',
          feedbackTarget: 'task-2.sequential_dependencies',
        },
      ],
    },
  ],
};

export default function PlanFeedbackPreviewPage() {
  const initSession = useChatSessionStore((state) => state.initSession);
  const setProject = useProjectStore((state) => state.setProject);

  useEffect(() => {
    const now = new Date().toISOString();

    setProject({
      projectMemberId: 1,
      projectId: 1,
      projectName: 'PLAN field feedback preview',
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
          messageId: 'dev-user-1',
          senderType: 'USER',
          messageType: 'TOOL_PLAN_REQUEST',
          contentType: 'TEXT',
          content: 'system health reporter 도구를 구현해줘',
          createdAt: now,
        },
        {
          messageId: 'dev-assistant-1',
          senderType: 'ASSISTANT',
          messageType: 'TOOL_PLAN_RESPONSE',
          contentType: 'MARKDOWN',
          content: 'Tool PLAN generation completed.',
          createdAt: now,
        },
      ],
      plan: previewPlan,
      phase: 'REVIEW',
      toolId: null,
      toolPlanGroupId: 'dev-preview-group',
      toolPlanId: 'dev-preview-plan',
      runId: null,
      planStatus: 'REVIEW',
      createdTool: null,
      toolResult: null,
      title: 'PLAN field feedback preview',
      isClosed: false,
      planVersion: 1,
      draftVersion: 1,
    });
  }, [initSession, setProject]);

  return (
    <div className="h-screen bg-[#051424]">
      <ChatDashboard />
    </div>
  );
}
