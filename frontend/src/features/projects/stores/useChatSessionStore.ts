import { create } from 'zustand';
import type {
  ChatMessage,
  CreatedToolRecovery,
  DraftPhase,
  ProgressInfo,
  StructuredPlan,
  ToolPlanMode
} from '../types/chat';

interface ChatSessionState {
  messages: ChatMessage[];
  mode: ToolPlanMode;
  currentPlan: StructuredPlan | null;
  draftPhase: DraftPhase;
  planStatus: string | null;
  currentRunId: string | null;
  currentToolPlanGroupId: string | null;
  currentToolPlanId: string | null;
  currentToolId: string | null;
  createdTool: CreatedToolRecovery | null;
  isGenerating: boolean;
  progressInfo: ProgressInfo | null;
  commentMode: boolean;
  draftComments: Record<string, string>;
  toolResult: Record<string, unknown> | null;
  activeTab: 'plan' | 'result';
  isBuilding: boolean;
  draftVersion: number;
  planVersion: number;
  abortController: AbortController | null;
  title: string;
  isClosed: boolean;

  initSession: (data: {
    messages: ChatMessage[];
    plan: StructuredPlan | null;
    phase: DraftPhase;
    toolId: string | null;
    toolPlanGroupId?: string | null;
    toolPlanId?: string | null;
    runId?: string | null;
    planStatus?: string | null;
    createdTool?: CreatedToolRecovery | null;
    toolResult: Record<string, unknown> | null;
    title: string;
    isClosed: boolean;
    planVersion?: number;
    draftVersion?: number;
  }) => void;
  setMode: (mode: ToolPlanMode) => void;
  setToolResult: (result: Record<string, unknown> | null) => void;
  setActiveTab: (tab: 'plan' | 'result') => void;
  setIsBuilding: (isBuilding: boolean) => void;
  addMessage: (msg: ChatMessage) => void;
  updateLastMessageContent: (chunk: string) => void;
  setCurrentPlan: (plan: StructuredPlan | null) => void;
  setDraftPhase: (phase: DraftPhase) => void;
  setPlanStatus: (status: string | null) => void;
  setIsGenerating: (isGen: boolean) => void;
  setProgressInfo: (info: ProgressInfo | null) => void;
  setCommentMode: (mode: boolean) => void;
  setDraftComment: (blockId: string, comment: string) => void;
  clearDraftComments: () => void;
  setCurrentRunId: (runId: string | null) => void;
  setCurrentToolId: (toolId: string | null) => void;
  setCurrentToolPlanGroupId: (planGroupId: string | null) => void;
  setCurrentToolPlanId: (planId: string | null) => void;
  setCreatedTool: (createdTool: CreatedToolRecovery | null) => void;
  setDraftVersion: (version: number) => void;
  setPlanVersion: (version: number) => void;
  setAbortController: (ctrl: AbortController | null) => void;
  abortGeneration: () => void;
  updateTitle: (title: string) => void;
  setClosed: (isClosed: boolean) => void;
}

export const useChatSessionStore = create<ChatSessionState>((set, get) => ({
  messages: [],
  mode: 'PLAN',
  currentPlan: null,
  draftPhase: null,
  planStatus: null,
  currentRunId: null,
  currentToolPlanGroupId: null,
  currentToolPlanId: null,
  currentToolId: null,
  createdTool: null,
  isGenerating: false,
  progressInfo: null,
  commentMode: false,
  draftComments: {},
  draftVersion: 0,
  planVersion: 0,
  toolResult: null,
  activeTab: 'plan',
  isBuilding: false,
  abortController: null,
  title: '',
  isClosed: false,

  initSession: ({
    messages,
    plan,
    phase,
    toolId,
    toolPlanGroupId,
    toolPlanId,
    runId,
    planStatus,
    createdTool,
    toolResult,
    title,
    isClosed,
    planVersion,
    draftVersion
  }) => set({
    messages,
    currentPlan: plan,
    draftPhase: phase,
    planStatus: planStatus || phase,
    currentRunId: runId || null,
    currentToolId: toolId,
    currentToolPlanGroupId: toolPlanGroupId || null,
    currentToolPlanId: toolPlanId || null,
    createdTool: createdTool || null,
    toolResult: toolResult || null,
    activeTab: createdTool || toolResult ? 'result' : 'plan',
    isBuilding: false,
    draftVersion: draftVersion || 0,
    planVersion: planVersion || 0,
    title,
    isClosed,
    isGenerating: false,
    progressInfo: null,
    commentMode: false,
    draftComments: {},
    abortController: null,
  }),

  setMode: (mode) => set({ mode }),

  addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),

  updateLastMessageContent: (chunk) => set((state) => {
    const messages = [...state.messages];
    if (messages.length > 0) {
      const last = messages[messages.length - 1];
      messages[messages.length - 1] = { ...last, content: last.content + chunk };
    }
    return { messages };
  }),

  setCurrentPlan: (plan) => set({ currentPlan: plan }),
  setDraftPhase: (phase) => set({ draftPhase: phase }),
  setPlanStatus: (status) => set({ planStatus: status }),
  setIsGenerating: (isGen) => set({ isGenerating: isGen }),
  setProgressInfo: (info) => set({ progressInfo: info }),
  setCommentMode: (mode) => set({ commentMode: mode }),
  setDraftComment: (blockId, comment) =>
    set((state) => ({
      draftComments: { ...state.draftComments, [blockId]: comment },
    })),
  clearDraftComments: () => set({ draftComments: {} }),

  setCurrentRunId: (runId) => set({ currentRunId: runId }),
  setCurrentToolId: (toolId) => set({ currentToolId: toolId }),
  setCurrentToolPlanGroupId: (planGroupId) => set({ currentToolPlanGroupId: planGroupId }),
  setCurrentToolPlanId: (planId) => set({ currentToolPlanId: planId }),
  setCreatedTool: (createdTool) => set({ createdTool }),
  setDraftVersion: (version) => set({ draftVersion: version }),
  setPlanVersion: (version) => set({ planVersion: version }),
  setToolResult: (result) => set({ toolResult: result }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setIsBuilding: (isBuilding) => set({ isBuilding }),
  setAbortController: (ctrl) => set({ abortController: ctrl }),
  abortGeneration: () => {
    const ctrl = get().abortController;
    if (ctrl) {
      ctrl.abort();
    }
    set({ isGenerating: false, abortController: null });
  },

  updateTitle: (title) => set({ title }),
  setClosed: (isClosed) => set({ isClosed }),
}));
