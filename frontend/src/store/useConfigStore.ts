import { create } from 'zustand';
import { orderApi } from '../api/order';

interface ConfigState {
    feeRate: number;
    taxRate: number;
    fetchTradePolicy: () => Promise<void>;
}

export const useConfigStore = create<ConfigState>((set) => ({
    feeRate: 0.00015, // 기본 수수료율 (0.015%)
    taxRate: 0.002,   // 기본 제세금 (0.2%)

    fetchTradePolicy: async () => {
        try {
            const policy = await orderApi.getTradePolicy();
            set({ feeRate: policy.feeRate, taxRate: policy.taxRate });
        } catch (error) {
            console.error('Failed to fetch trade policy, using default values:', error);
            // 에러 발생 시 기본값 유지 (이미 초기값으로 설정됨)
        }
    },
}));
