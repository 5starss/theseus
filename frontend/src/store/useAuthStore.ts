import { create } from 'zustand';

interface User {
  id: number;
  name: string;
  systemRole: string;
}

interface AuthState {
  accessToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  
  // Actions
  login: (accessToken: string, user: User) => void;
  logout: () => void;
  setAccessToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  accessToken: null,
  user: null,
  isAuthenticated: false,

  login: (accessToken, user) => set({ 
    accessToken, 
    user, 
    isAuthenticated: true 
  }),

  logout: () => set({ 
    accessToken: null, 
    user: null, 
    isAuthenticated: false 
  }),

  setAccessToken: (token) => set({ 
    accessToken: token 
  }),
}));
