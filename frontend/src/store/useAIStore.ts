import { create } from 'zustand';
import { aiApi, type AutoTradeStyle, type AgentStatus } from '../api/ai';
import type { AccountType } from '../api/account';

interface AIState {
    // Settings
    isAIOn: boolean;
    investStyle: AutoTradeStyle;
    
    // Status
    isAnalyzing: boolean;
    error: string | null;
    agentStatuses: AgentStatus[];
    pollingInterval: number | null;

    // Actions
    setError: (error: string | null) => void;
    setInvestStyle: (style: AutoTradeStyle) => void;
    toggleAutoTrade: (userId: number, accountType: AccountType) => Promise<void>;
    fetchConfig: (userId: number) => Promise<void>;
    fetchAgentStatus: (userId: number) => Promise<void>;
    startPolling: (userId: number) => void;
    stopPolling: () => void;
}

export const useAIStore = create<AIState>((set, get) => ({
    isAIOn: false,
    investStyle: 'LONG',
    isAnalyzing: false,
    error: null,
    agentStatuses: [],
    pollingInterval: null,

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

            const isNowOn = response.config.enabled;
            set({ 
                isAIOn: isNowOn,
                isAnalyzing: false 
            });

            if (isNowOn) {
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
            const isNowOn = config.enabled;
            set({ 
                isAIOn: isNowOn,
                investStyle: config.invest_style
            });

            if (isNowOn) {
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

            // 현재 시간 기준 슬롯 판별 (오전 12시 기준)
            const currentSlot = new Date().getHours() < 12 ? 'morning' : 'afternoon';

            // 최적화: 현재 슬롯의 모든 종목 분석이 완료되었다면 더 이상 폴링할 필요 없음
            const currentSlotStatuses = statuses.filter(s => s.strategySlot === currentSlot);
            const isAllFinished = currentSlotStatuses.length > 0 && currentSlotStatuses.every(s => s.judgeReceived);
            
            if (isAllFinished) {
                console.log(`All AI analyses for ${currentSlot} finished. Stopping polling.`);
                const interval = get().pollingInterval;
                if (interval) {
                    window.clearInterval(interval);
                    set({ pollingInterval: null });
                }
            }
        } catch (error: any) {
            console.error('Error fetching agent status:', error);
            
            // 500 에러 등 서버 오류 발생 시 폴링 중단 및 알림
            if (error.response?.status === 500) {
                set({ error: 'AI 서버 상태가 불안정합니다. 잠시 후 다시 시도해주세요.' });
                get().stopPolling();
            }
        }
    },

    // 폴링 시작 (3초 간격)
    startPolling: (userId) => {
        if (get().pollingInterval) return;

        // 즉시 한 번 실행
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
