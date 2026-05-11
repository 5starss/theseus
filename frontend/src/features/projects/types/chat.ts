export type DraftPhase = null | 'DRAFT' | 'PLAN' | 'REVIEW' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'BUILDING' | 'BUILT' | 'FAILED';
export type SenderType = 'USER' | 'ASSISTANT' | 'SYSTEM' | 'SYSTEM_NOTICE' | 'TOOL_FEEDBACK' | 'TOOL_APPROVAL_REQUEST';
export type MessageType =
  | 'CHAT'
  | 'TOOL_DRAFT_REQUEST'
  | 'TOOL_DRAFT_RESPONSE'
  | 'TOOL_REGENERATE_REQUEST'
  | 'TOOL_REGENERATE_RESPONSE'
  | 'TOOL_PLAN_REQUEST'
  | 'TOOL_PLAN_RESPONSE'
  | 'TOOL_FEEDBACK'
  | 'TOOL_APPROVAL_REQUEST'
  | 'SYSTEM_NOTICE';
export type ContentType = 'TEXT' | 'MARKDOWN' | 'JSON';

export interface ChatMessage {
  messageId: number | string;
  senderType: SenderType;
  messageType?: MessageType;
  contentType?: ContentType;
  content: string;
  toolId?: number | string;
  messageOrder?: number;
  createdAt: string;
}

export interface PlanBlock {
  blockId: string;
  title: string;
  content: string;
}

export interface StructuredPlan {
  version: string | number;
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

export interface CurrentPlanResponse {
  runId: string | null;
  toolPlanGroupId: number | null;
  toolPlanId: number | null;
  planVersion: number | null;
  status: string;
}

export interface CreatedToolResponse {
  toolId: number;
  sourceToolPlanId: number | null;
  status: string;
}

export type CurrentPlanRecovery = CurrentPlanResponse;
export type CreatedToolRecovery = CreatedToolResponse;

export interface ChatSessionDetailResponse {
  sessionId: number;
  projectId: number;
  projectMemberId: number;
  title: string;
  isClosed: boolean;
  closedAt: string | null;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
  currentPlan: CurrentPlanResponse | null;
  createdTool: CreatedToolResponse | null;
}

export const ToolPlanMode = {
  ASK: 'ASK',
  PLAN: 'PLAN',
  AGENT: 'AGENT'
} as const;

export type ToolPlanMode = typeof ToolPlanMode[keyof typeof ToolPlanMode];

export interface ToolPlanGenerationResponse {
  runId: string;
  projectId: number;
  sessionId: number;
  status: string;
  sseUrl: string;
}

export interface ToolBuildGenerationResponse {
  toolId: number;
  sseUrl: string;
}

export interface ToolPlanGenerationRequest {
  mode: ToolPlanMode;
  prompt: string;
}

export interface ToolPlanRegenerationRequest {
  mode: ToolPlanMode;
  basePlanVersion: number;
  feedbackItems: Array<{ blockId: string; comment: string }>;
}

export interface ToolPlanDetailResponse {
  toolPlanId: number;
  toolPlanGroupId: number;
  projectId: number;
  chatSessionId: number;
  createdByProjectMemberId: number;
  baseToolPlanId: number | null;
  planVersion: number;
  status: string;
  mode: ToolPlanMode;
  requestedPrompt: string | null;
  rawMarkdown: string;
  structuredPlanJson: string;
  planSnapshot: string;
  createdAt: string;
  updatedAt: string;
}

export interface ToolPlanRunStateResponse {
  runId: string;
  projectId: number;
  chatSessionId: number;
  toolPlanGroupId?: number | null;
  toolPlanId?: number | null;
  planVersion?: number | null;
  eventType: string;
  status: string;
  progressRate?: number;
  message?: string;
  content?: string;
  errorCode?: string;
  errorMessage?: string;
  updatedAt?: string;
}

export interface ToolBuildGenerationStateResponse {
  status: string;
  toolId: number;
  draftVersion: number;
  draftPhase: string;
  progressRate?: number;
  message?: string;
  content?: string;
}

export interface ToolGenerationSseEvent {
  eventType: string;
  projectId: number;
  chatSessionId: number;
  toolPlanGroupId?: number;
  toolPlanId?: number;
  toolId?: number;
  runId?: string;
  status?: string;
  draftPhase?: string;
  progressRate?: number;
  message?: string;
  content?: string;
  planVersion?: number;
  draftVersion?: number;
  errorCode?: string;
  errorMessage?: string;
  updatedAt: string;
}
