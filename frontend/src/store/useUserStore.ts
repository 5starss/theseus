import { create } from 'zustand';
import { userApi } from '../api/user';
import type { UserProfile, InvestmentStyle } from '../api/user';

interface UserState {
    profile: UserProfile | null;
    isLoading: boolean;
    error: string | null;
    fetchProfile: () => Promise<void>;
    updateInvestmentStyle: (style: InvestmentStyle) => Promise<void>;
}

export const useUserStore = create<UserState>((set) => ({
    profile: null,
    isLoading: false,
    error: null,

    fetchProfile: async () => {
        set({ isLoading: true, error: null });
        try {
            const profile = await userApi.getUserProfile();
            set({ profile, isLoading: false });
        } catch (_err) {
            set({ error: (_err as Error).message, isLoading: false });
        }
    },

    updateInvestmentStyle: async (style: InvestmentStyle) => {
        set({ isLoading: true, error: null });
        try {
            const updatedProfile = await userApi.updateInvestmentStyle(style);
            set({ profile: updatedProfile, isLoading: false });
        } catch (_err) {
            set({ error: (_err as Error).message, isLoading: false });
        }
    }
}));
