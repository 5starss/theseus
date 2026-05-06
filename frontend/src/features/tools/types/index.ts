export interface ToolItem {
  id: string;
  name: string;
  description: string;
  type: 'BLUE' | 'AMBER' | 'ROSE';
  iconName: string;
}

export interface ToolListResponse {
  tools: ToolItem[];
}
