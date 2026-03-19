import { create } from 'zustand';

export type InvestStyle = 'LONG' | 'SHORT'; // 장투 / 단타

interface AIState {
    isAIOn: boolean;
    investStyle: InvestStyle;
    setAIOn: (isOn: boolean) => void;
    setInvestStyle: (style: InvestStyle) => void;
    toggleAI: () => void;
}

export const useAIStore = create<AIState>((set) => ({
    isAIOn: false,
    investStyle: 'LONG',
    setAIOn: (isOn) => set({ isAIOn: isOn }),
    setInvestStyle: (style) => set({ investStyle: style }),
    toggleAI: () => set((state) => ({ isAIOn: !state.isAIOn })),
}));
