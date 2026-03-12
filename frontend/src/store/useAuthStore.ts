import { create } from 'zustand';

interface AuthState {
    isLoggedIn: boolean;
    user: { name: string; email: string } | null;
    token: string | null;
    login: (email: string, token: string, nickname: string) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    isLoggedIn: !!localStorage.getItem('accessToken'),
    user: localStorage.getItem('userEmail') ? { name: localStorage.getItem('userNickname') || '회원', email: localStorage.getItem('userEmail')! } : null,
    token: localStorage.getItem('accessToken'),
    login: (email, token, nickname) => {
        localStorage.setItem('accessToken', token);
        localStorage.setItem('userEmail', email);
        localStorage.setItem('userNickname', nickname);
        set({ isLoggedIn: true, user: { name: nickname, email }, token });
    },
    logout: () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('userNickname');
        set({ isLoggedIn: false, user: null, token: null });
    },
}));
