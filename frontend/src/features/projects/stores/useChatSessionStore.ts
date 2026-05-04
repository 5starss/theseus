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

  // Actions
  addMessage: (msg: ChatMessage) => void;
  setPlan: (plan: StructuredPlan) => void;
  setDraftPhase: (phase: DraftPhase) => void;
  setIsGenerating: (isGen: boolean) => void;
  setProgressInfo: (info: ProgressInfo | null) => void;
  setCommentMode: (mode: boolean) => void;
  setDraftComment: (blockId: string, comment: string) => void;
  clearDraftComments: () => void;
}

export const useChatSessionStore = create<ChatSessionState>((set) => ({
  messages: [],
  currentPlan: null,
  draftPhase: null,
  isGenerating: false,
  progressInfo: null,
  commentMode: false,
  draftComments: {},

  addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
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
}));
