import { create } from 'zustand';
import { aiApi, type AutoTradeStyle, type AgentStatus } from '../api/ai';
import type { AccountType } from '../api/account';

interface AIState {
    // Settings
    isAIOn: boolean;
    investStyle: AutoTradeStyle;
    targetCount: number; // 분석을 기다려야 하는 목표 종목 수 (관심종목 개수 기반)

    // Status
    isAnalyzing: boolean;
    error: string | null;
    agentStatuses: AgentStatus[];
    pollingInterval: number | null;

    // Actions
    setError: (error: string | null) => void;
    setInvestStyle: (style: AutoTradeStyle) => void;
    setTargetCount: (count: number) => void;
    toggleAutoTrade: (userId: number, accountType: AccountType) => Promise<void>;
    fetchConfig: (userId: number) => Promise<void>;
    fetchAgentStatus: (userId: number) => Promise<void>;
    startPolling: (userId: number) => void;
    stopPolling: () => void;
}

export const useAIStore = create<AIState>((set, get) => ({
    isAIOn: false,
    investStyle: 'LONG',
    targetCount: 0,
    isAnalyzing: false,
    error: null,
    agentStatuses: [],
    pollingInterval: null,

    setError: (error) => set({ error }),

    setInvestStyle: (style) => set({ investStyle: style }),

    setTargetCount: (count) => set({ targetCount: count }),

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

            const config = response.config;
            set({
                isAIOn: config.enabled,
                isAnalyzing: false
            });

            if (config.enabled) {
                get().startPolling(userId);
            } else {
                get().stopPolling();
            }
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
                investStyle: config.invest_style,
            });

            if (config.enabled) {
                get().startPolling(userId);
            }
        } catch (error) {
            console.error('Failed to fetch AI config:', error);
        }
    },

    // 실시간 에이전트 상태 조회
    fetchAgentStatus: async (userId) => {
        try {
            const statuses = await aiApi.getAgentStatus(userId);
            set({ agentStatuses: statuses, error: null });

            // 현재 시간 기준 슬롯 판별
            const currentSlot = new Date().getHours() < 12 ? 'morning' : 'afternoon';
            const currentSlotStatuses = statuses.filter(s => s.strategySlot === currentSlot);

            // 목표 개수 (관심종목 수, 최대 3)
            const goal = get().targetCount;

            // 중단 조건:
            // 1. 목표 개수가 0보다 큼
            // 2. 현재 슬롯의 리포트 개수가 목표 개수 이상임
            // 3. 그 모든 리포트의 judgeReceived가 true임
            const isAllFinished =
                goal > 0 &&
                currentSlotStatuses.length >= goal &&
                currentSlotStatuses.every(s => s.judgeReceived);

            if (isAllFinished) {
                console.log(`AI Analysis Complete: ${currentSlotStatuses.length}/${goal} tickers finished. Polling stopped.`);
                const interval = get().pollingInterval;
                if (interval) {
                    window.clearInterval(interval);
                    set({ pollingInterval: null });
                }
            }
        } catch (error: any) {
            console.error('Error fetching agent status:', error);

            if (error.response?.status === 500) {
                set({ error: 'AI 서버 상태가 불안정합니다. 잠시 후 다시 시도해주세요.' });
                get().stopPolling();
            }
        }
    },

    // 폴링 시작 (3초 간격)
    startPolling: (userId) => {
        if (get().pollingInterval) return;

        get().fetchAgentStatus(userId);

        const interval = window.setInterval(() => {
            get().fetchAgentStatus(userId);
        }, 3000);

        set({ pollingInterval: interval });
    },

    // 폴링 중지
    stopPolling: () => {
        const interval = get().pollingInterval;
        if (interval) {
            window.clearInterval(interval);
            set({ pollingInterval: null, agentStatuses: [] });
        }
    }
}));
