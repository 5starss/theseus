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
