import { create } from 'zustand';

interface AuthState {
    isLoggedIn: boolean;
    user: { name: string; loginId: string } | null;
    login: (loginId: string) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    isLoggedIn: false, // 초기 로그인 상태는 false
    user: null,
    login: (loginId) => set({ isLoggedIn: true, user: { name: '김싸피', loginId } }),
    logout: () => set({ isLoggedIn: false, user: null }),
}));
