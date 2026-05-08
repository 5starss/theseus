import { create } from 'zustand';
import type { ChatMessage, StructuredPlan, ProgressInfo, DraftPhase } from '../types/chat';

interface ChatSessionState {
  messages: ChatMessage[];
  currentPlan: StructuredPlan | null;
  draftPhase: DraftPhase;
  isGenerating: boolean;
  progressInfo: ProgressInfo | null;
  commentMode: boolean;
  draftComments: Record<string, string>; // blockId -> comment
  toolResult: Record<string, unknown> | null;
  activeTab: 'plan' | 'result';
  isBuilding: boolean;
  currentToolId: string | null;
  draftVersion: number;
  abortController: AbortController | null;
  title: string;
  isClosed: boolean;

  // Actions
  initSession: (data: {
    messages: ChatMessage[];
    plan: StructuredPlan | null;
    phase: DraftPhase;
    toolId: string | null;
    toolResult: Record<string, unknown> | null;
    title: string;
    isClosed: boolean;
  }) => void;
  setToolResult: (result: Record<string, unknown> | null) => void;
  setActiveTab: (tab: 'plan' | 'result') => void;
  setIsBuilding: (isBuilding: boolean) => void;
  addMessage: (msg: ChatMessage) => void;
  updateLastMessageContent: (chunk: string) => void;
  setPlan: (plan: StructuredPlan) => void;
  setDraftPhase: (phase: DraftPhase) => void;
  setIsGenerating: (isGen: boolean) => void;
  setProgressInfo: (info: ProgressInfo | null) => void;
  setCommentMode: (mode: boolean) => void;
  setDraftComment: (blockId: string, comment: string) => void;
  clearDraftComments: () => void;
  setCurrentToolId: (toolId: string | null) => void;
  setDraftVersion: (version: number) => void;
  setAbortController: (ctrl: AbortController | null) => void;
  abortGeneration: () => void;
  updateTitle: (title: string) => void;
  setClosed: (isClosed: boolean) => void;
}

export const useChatSessionStore = create<ChatSessionState>((set, get) => ({
  messages: [],
  currentPlan: null,
  draftPhase: null,
  isGenerating: false,
  progressInfo: null,
  commentMode: false,
  draftComments: {},
  currentToolId: null,
  draftVersion: 0,
  toolResult: null,
  activeTab: 'plan',
  isBuilding: false,
  abortController: null,
  title: '',
  isClosed: false,

  initSession: ({ messages, plan, phase, toolId, toolResult, title, isClosed }) => set({
    messages,
    currentPlan: plan,
    draftPhase: phase,
    currentToolId: toolId,
    toolResult: toolResult || null,
    activeTab: (phase === 'REVIEW' || phase === 'APPROVED') && toolResult ? 'result' : 'plan',
    isBuilding: false,
    draftVersion: 0,
    title,
    isClosed,
    isGenerating: false,
    progressInfo: null,
    commentMode: false,
    draftComments: {},
    abortController: null,
  }),

  addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
  
  updateLastMessageContent: (chunk) => set((state) => {
    const messages = [...state.messages];
    if (messages.length > 0) {
      const last = messages[messages.length - 1];
      messages[messages.length - 1] = { ...last, content: last.content + chunk };
    }
    return { messages };
  }),

  setPlan: (plan) => set({ currentPlan: plan }),
  setDraftPhase: (phase) => set({ draftPhase: phase }),
  setIsGenerating: (isGen) => set({ isGenerating: isGen }),
  setProgressInfo: (info) => set({ progressInfo: info }),
  setCommentMode: (mode) => set({ commentMode: mode }),
  setDraftComment: (blockId, comment) =>
    set((state) => ({
      draftComments: { ...state.draftComments, [blockId]: comment },
    })),
  clearDraftComments: () => set({ draftComments: {} }),
  
  setCurrentToolId: (toolId) => set({ currentToolId: toolId }),
  setDraftVersion: (version) => set({ draftVersion: version }),
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
