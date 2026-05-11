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

export interface ChatSessionState {
  messages: ChatMessage[];
  currentPlan: StructuredPlan | null;
  toolResult: Record<string, unknown> | null;
  draftPhase: DraftPhase;
  currentToolId: string | null;
  title: string;
  isClosed: boolean;
  isLoading: boolean;
  isGenerating: boolean;
  isBuilding: boolean;
  activeTab: 'plan' | 'result';
  progressInfo: ProgressInfo | null;
  draftVersion: number;
  abortController: AbortController | null;
}

// Tool Plan 생성/재생성 HTTP 응답
export interface ToolPlanGenerationResponse {
  runId: string;
  toolPlanId?: number;
  projectId: number;
  sessionId: number;
  status: string;
  planVersion?: number;
  sseUrl: string;
}

// Tool Build/Rebuild HTTP 응답
export interface ToolBuildGenerationResponse {
  toolId: number;
  projectId: number;
  sessionId: number;
  status: string;
  draftPhase?: string;
  draftVersion?: number;
  sseUrl: string;
}

// Tool Plan 생성 상태 조회 HTTP 응답
export interface ToolPlanGenerationStateResponse {
  projectId: number;
  chatSessionId: number;
  toolPlanId: number;
  runId: string;
  eventType: string;
  status: string;
  progressRate?: number;
  message?: string;
  content?: string;
  planVersion?: number;
  errorCode?: string;
  errorMessage?: string;
  updatedAt: string;
}

// Tool Build 생성 상태 조회 HTTP 응답
export interface ToolBuildGenerationStateResponse {
  projectId: number;
  chatSessionId: number;
  toolId: number;
  eventType: string;
  status: string;
  draftPhase: string;
  progressRate?: number;
  message?: string;
  content?: string;
  draftVersion?: number;
  errorCode?: string;
  errorMessage?: string;
  updatedAt: string;
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
