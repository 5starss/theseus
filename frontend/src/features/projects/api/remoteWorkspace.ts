import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type {
  RemoteWorkspaceConnectionTestResponse,
  RemoteWorkspaceCreateRequest,
  RemoteWorkspaceResponse,
} from '../types/project';

export const remoteWorkspaceApi = {
  getRemoteWorkspaces: async (projectId: string) => {
    const response = await apiClient.get<ApiResponse<RemoteWorkspaceResponse[]>>(
      `/api/v1/projects/${projectId}/remote-workspaces`
    );
    return response.data.result;
  },

  createRemoteWorkspace: async (
    projectId: string,
    payload: RemoteWorkspaceCreateRequest
  ) => {
    const response = await apiClient.post<ApiResponse<RemoteWorkspaceResponse>>(
      `/api/v1/projects/${projectId}/remote-workspaces`,
      payload
    );
    return response.data.result;
  },

  deleteRemoteWorkspace: async (projectId: string, remoteWorkspaceId: number) => {
    const response = await apiClient.patch<ApiResponse<RemoteWorkspaceResponse>>(
      `/api/v1/projects/${projectId}/remote-workspaces/${remoteWorkspaceId}/delete`
    );
    return response.data.result;
  },

  testConnection: async (projectId: string, remoteWorkspaceId: number) => {
    const response = await apiClient.post<ApiResponse<RemoteWorkspaceConnectionTestResponse>>(
      `/api/v1/projects/${projectId}/remote-workspaces/${remoteWorkspaceId}/test-connection`
    );
    return response.data.result;
  },
};
