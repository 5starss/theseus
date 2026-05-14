export interface MyProjectResponse {
  projectId: number;
  name: string;
  description: string;
  projectStatus: 'ACTIVE' | 'INACTIVE';
  projectRole: 'ADMIN' | 'MEMBER';
  memberStatus: 'ACTIVE' | 'INACTIVE';
  projectAdminUserId: number;
  projectAdminEmployeeNumber: string;
  projectAdminName: string;
  isProjectAdminUser: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectMemberResponse {
  projectMemberId: number;
  projectId: number;
  projectName: string;
  userId: number;
  employeeNumber: string;
  name: string;
  projectRole: 'ADMIN' | 'MANAGER' | 'MEMBER';
  accessLevel: number;
  canCreateTool: boolean;
  canUseTool: boolean;
  canUpdateTool: boolean;
  canDeleteTool: boolean;
  status: 'IN_PROGRESS' | 'COMPLETED';
  isProjectAdminUser: boolean;
  createdByUserId: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface RemoteWorkspaceResponse {
  remoteWorkspaceId: number;
  projectId: number;
  createdByProjectMemberId: number;
  name: string;
  host: string;
  port: number;
  username: string;
  privateKeyPath: string | null;
  basePath: string;
  allowWriteExecution: boolean;
  status: 'ACTIVE' | 'DELETED';
  createdAt: string;
  updatedAt: string;
}

export interface RemoteWorkspaceCreateRequest {
  name: string;
  host: string;
  port: number;
  username: string;
  password?: string;
  privateKeyPath?: string;
  basePath: string;
  allowWriteExecution?: boolean;
}

export interface RemoteWorkspaceConnectionTestResponse {
  remoteWorkspaceId: number;
  available: boolean;
  message: string;
}
