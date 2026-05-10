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

// Tool 생성/재생성 HTTP 응답
export interface ToolGenerationRunResponse {
  runId: string;
  toolId: number;
  projectId: number;
  sessionId: number;
  status: string;
  draftPhase: string;
  draftVersion: number;
  sseUrl: string;
}

// Tool 생성/재생성 상태 조회 HTTP 응답
export interface ToolGenerationStateResponse {
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
  eventType: 'connected' | 'progress' | 'chunk' | 'completed' | 'failed';
  projectId: number;
  chatSessionId: number;
  toolId: number;
  status?: string;
  draftPhase?: string;
  progressRate?: number;
  message?: string;
  content?: string;
  draftVersion?: number;
  errorCode?: string;
  errorMessage?: string;
  updatedAt: string;
}
