import { create } from 'zustand';

interface AuthState {
    isLoggedIn: boolean;
    user: { id: number; name: string; email: string } | null;
    token: string | null;
    login: (id: number, email: string, token: string, nickname: string) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    isLoggedIn: !!localStorage.getItem('accessToken'),
    user: localStorage.getItem('userEmail') ? { 
        id: Number(localStorage.getItem('userId')),
        name: localStorage.getItem('userNickname') || '회원', 
        email: localStorage.getItem('userEmail')! 
    } : null,
    token: localStorage.getItem('accessToken'),
    login: (id, email, token, nickname) => {
        localStorage.setItem('accessToken', token);
        localStorage.setItem('userEmail', email);
        localStorage.setItem('userNickname', nickname);
        localStorage.setItem('userId', id.toString());
        set({ isLoggedIn: true, user: { id, name: nickname, email }, token });
    },
    logout: () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('userNickname');
        localStorage.removeItem('userId');
        set({ isLoggedIn: false, user: null, token: null });
    },
}));
