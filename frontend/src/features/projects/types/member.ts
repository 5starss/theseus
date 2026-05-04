export interface ProjectMemberCreateRequest {
  employeeNumber: string;
  projectRole?: 'ADMIN' | 'MANAGER' | 'MEMBER';
  accessLevel?: number;
  canCreateTool?: boolean;
  canUseTool?: boolean;
  canUpdateTool?: boolean;
  canDeleteTool?: boolean;
}

export interface ProjectMemberUpdateRequest {
  projectRole?: 'ADMIN' | 'MANAGER' | 'MEMBER';
  accessLevel?: number;
  canCreateTool?: boolean;
  canUseTool?: boolean;
  canUpdateTool?: boolean;
  canDeleteTool?: boolean;
  status?: 'IN_PROGRESS' | 'COMPLETED';
}
