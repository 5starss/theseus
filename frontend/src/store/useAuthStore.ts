import { create } from 'zustand';

interface AuthState {
    isLoggedIn: boolean;
    user: { name: string; email: string } | null;
    token: string | null;
    login: (email: string, token: string) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    isLoggedIn: !!localStorage.getItem('accessToken'),
    user: localStorage.getItem('userEmail') ? { name: '회원', email: localStorage.getItem('userEmail')! } : null,
    token: localStorage.getItem('accessToken'),
    login: (email, token) => {
        localStorage.setItem('accessToken', token);
        localStorage.setItem('userEmail', email);
        set({ isLoggedIn: true, user: { name: '회원', email }, token });
    },
    logout: () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('userEmail');
        set({ isLoggedIn: false, user: null, token: null });
    },
}));
