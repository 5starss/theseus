import { create } from 'zustand';
import type { ProjectMemberResponse } from '../api';

interface ProjectState {
  currentProject: ProjectMemberResponse | null;
  isLoading: boolean;
  errorMessage: string | null;
  setProject: (project: ProjectMemberResponse | null) => void;
  setIsLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  currentProject: null,
  isLoading: true,
  errorMessage: null,
  setProject: (project) => set({ currentProject: project, isLoading: false, errorMessage: null }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ errorMessage: error, isLoading: false }),
  reset: () => set({ currentProject: null, isLoading: true, errorMessage: null }),
}));
