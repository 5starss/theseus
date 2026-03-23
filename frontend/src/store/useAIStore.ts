import { create } from 'zustand';
import { aiApi, type AutoTradeStyle } from '../api/ai';
import type { AccountType } from '../api/account';

interface AIState {
    // Settings
    isAIOn: boolean;
    investStyle: AutoTradeStyle;
    
    // Status
    isAnalyzing: boolean;
    error: string | null;

    // Actions
    setError: (error: string | null) => void;
    setInvestStyle: (style: AutoTradeStyle) => void;
    toggleAutoTrade: (userId: number, accountType: AccountType) => Promise<void>;
    fetchConfig: (userId: number) => Promise<void>;
}

export const useAIStore = create<AIState>((set, get) => ({
    isAIOn: false,
    investStyle: 'LONG',
    isAnalyzing: false,
    error: null,

    setError: (error) => set({ error }),

    setInvestStyle: (style) => set({ investStyle: style }),

    // 자동 매매 설정 업데이트
    toggleAutoTrade: async (userId, accountType) => {
        const nextState = !get().isAIOn;
        set({ isAnalyzing: true, error: null });

        try {
            const response = await aiApi.updateAutoTradeConfig(userId, {
                enabled: nextState,
                invest_style: get().investStyle,
                account_type: accountType,
            });

            set({ 
                isAIOn: response.config.enabled,
                isAnalyzing: false 
            });
        } catch (error) {
            console.error('Failed to toggle auto trade:', error);
            set({ error: '설정 반영에 실패했습니다.', isAnalyzing: false });
        }
    },

    // 초기 설정 로드
    fetchConfig: async (userId) => {
        try {
            const config = await aiApi.getAutoTradeConfig(userId);
            set({ 
                isAIOn: config.enabled,
                investStyle: config.invest_style
            });
        } catch (error) {
            console.error('Failed to fetch AI config:', error);
        }
    }
}));
