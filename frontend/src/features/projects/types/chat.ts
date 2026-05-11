export type DraftPhase = null | 'DRAFT' | 'PLAN' | 'REVIEW' | 'APPROVED' | 'REJECTED';
export type SenderType = 'USER' | 'ASSISTANT' | 'SYSTEM' | 'SYSTEM_NOTICE' | 'TOOL_FEEDBACK' | 'TOOL_APPROVAL_REQUEST';
export type MessageType = 'CHAT' | 'TOOL_DRAFT_REQUEST' | 'TOOL_DRAFT_RESPONSE' | 'TOOL_REGENERATE_REQUEST' | 'TOOL_REGENERATE_RESPONSE' | 'TOOL_FEEDBACK' | 'SYSTEM_NOTICE';
export type ContentType = 'TEXT' | 'MARKDOWN' | 'JSON';

export interface ChatMessage {
  messageId: number | string;
  senderType: SenderType;
  messageType?: MessageType;
  contentType?: ContentType;
  content: string;
  toolId?: number | string;
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

// 세션 상세 조회 API 응답 (GET /sessions/:sessionId)
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

// Tool Plan 생성/재생성 HTTP 응답
export interface ToolPlanGenerationResponse {
  runId: string;
  toolPlanId: number;
  sseUrl: string;
}

// Tool Build 생성 HTTP 응답
export interface ToolBuildGenerationResponse {
  toolId: number;
  sseUrl: string;
}

// Tool Plan 생성 요청 DTO (Backend spec)
export interface ToolPlanGenerationRequest {
  mode: ToolPlanMode;
  prompt: string;
}

// Tool Plan 재생성 요청 DTO (Backend spec)
export interface ToolPlanRegenerationRequest {
  mode: ToolPlanMode;
  basePlanVersion: number;
  feedbackItems: Array<{ blockId: string; comment: string }>;
}

// Tool Plan 상태 조회 응답
export interface ToolPlanGenerationStateResponse {
  status: string;
  toolPlanId: number;
  runId?: string;
  planVersion: number;
  messages: ChatMessage[];
  currentPlan?: StructuredPlan;
  isClosed: boolean;
  title: string;
  progressRate?: number;
  message?: string;
  content?: string;
}

// Tool Build 상태 조회 응답
export interface ToolBuildGenerationStateResponse {
  status: string;
  toolId: number;
  draftVersion: number;
  draftPhase: string;
  progressRate?: number;
  message?: string;
  content?: string;
}

// SSE 이벤트 데이터 구조
export interface ToolGenerationSseEvent {
  eventType: 'CONNECTED' | 'PROGRESS' | 'CHUNK' | 'TOOL_PLAN_COMPLETED' | 'TOOL_GENERATION_COMPLETED' | 'ERROR';
  projectId: number;
  chatSessionId: number;
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
