import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface User {
  id: number;
  name: string;
  systemRole: 'SUPER_ADMIN' | 'USER';
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

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      isAuthenticated: false,

      login: (accessToken, user) => set({ 
        accessToken, 
        user, 
        isAuthenticated: true 
      }),

      logout: () => {
        set({ 
          accessToken: null, 
          user: null, 
          isAuthenticated: false 
        });
        // Clear persisted storage explicitly
        localStorage.removeItem('auth-storage');
      },

      setAccessToken: (token) => set({ 
        accessToken: token 
      }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
