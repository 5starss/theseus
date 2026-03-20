import api from './client';
import type { AccountType } from './account';

export type AutoTradeStyle = 'LONG' | 'SHORT';

export interface AutoTradeConfig {
    user_id: number;
    enabled: boolean;
    invest_style: AutoTradeStyle;
    account_type: AccountType;
    tickers: string[];
    max_tickers_per_cycle: number;
}

export interface AutoTradeResponse {
    status: string;
    config: AutoTradeConfig;
}

export const aiApi = {
    // 자동 매매 설정 저장 및 활성화
    // POST /api/v1/ai/trade/auto/config?user_id=1
    updateAutoTradeConfig: async (userId: number, data: {
        enabled: boolean;
        invest_style: AutoTradeStyle;
        account_type: AccountType;
        tickers?: string[];
    }): Promise<AutoTradeResponse> => {
        try {
            const response = await api.post<AutoTradeResponse>(`/api/v1/ai/trade/auto/config`, {
                enabled: data.enabled,
                invest_style: data.invest_style,
                account_type: data.account_type,
                tickers: data.tickers || [],
                max_tickers_per_cycle: 3
            }, {
                params: { user_id: userId }
            });
            
            return response.data;
        } catch (error) {
            console.error('Error updating auto trade config:', error);
            throw error;
        }
    },

    // 현재 자동 매매 설정 조회
    // GET /api/v1/ai/trade/auto/config?user_id=1
    getAutoTradeConfig: async (userId: number): Promise<AutoTradeConfig> => {
        try {
            const response = await api.get<{ status: string; config: AutoTradeConfig }>(`/api/v1/ai/trade/auto/config`, {
                params: { user_id: userId }
            });
            return response.data.config;
        } catch (error) {
            console.error('Error fetching auto trade config:', error);
            throw error;
        }
    }
};
