import { create } from 'zustand';
import type { ProjectMemberResponse } from '../api';

interface ProjectState {
  currentProject: ProjectMemberResponse | null;
  isLoading: boolean;
  errorMessage: string | null;
  sessionFetchTrigger: number;
  setProject: (project: ProjectMemberResponse | null) => void;
  setIsLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  refreshSessions: () => void;
  reset: () => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  currentProject: null,
  isLoading: true,
  errorMessage: null,
  sessionFetchTrigger: 0,
  setProject: (project) => set({ currentProject: project, isLoading: false, errorMessage: null }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ errorMessage: error, isLoading: false }),
  refreshSessions: () => set((state) => ({ sessionFetchTrigger: state.sessionFetchTrigger + 1 })),
  reset: () => set({ currentProject: null, isLoading: true, errorMessage: null, sessionFetchTrigger: 0 }),
}));
