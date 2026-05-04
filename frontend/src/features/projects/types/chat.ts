export type DraftPhase = null | 'DRAFT' | 'PLAN' | 'REVIEW' | 'APPROVED' | 'REJECTED';
export type SenderType = 'USER' | 'ASSISTANT' | 'SYSTEM_NOTICE' | 'TOOL_FEEDBACK' | 'TOOL_APPROVAL_REQUEST';

export interface ChatMessage {
  id: string;
  sender: SenderType;
  content: string;
  createdAt: string;
}

export interface PlanBlock {
  blockId: string;
  title: string;
  content: string;
}

export interface StructuredPlan {
  version: string;
  blocks: PlanBlock[];
}

export interface ProgressInfo {
  step: string;
  message: string;
  percent: number;
}

export interface ChatSession {
  sessionId: number;
  projectId: number;
  projectMemberId: number;
  title: string;
  isClosed: boolean;
  closedAt: string | null;
  createdAt: string;
  updatedAt: string;
}
