import { createBrowserRouter } from 'react-router-dom';
import AuthLayout from '@/layouts/AuthLayout';
import LoginPage from '@/pages/auth/LoginPage';
import AdminLayout from '@/layouts/AdminLayout';
import SuperAdminPage from '@/pages/admin/SuperAdminPage';
import UserLayout from '@/layouts/UserLayout';
import ProjectListPage from '@/pages/user/ProjectListPage';
import ProjectLayout from '@/layouts/ProjectLayout';
import ProtectedRoute from './ProtectedRoute';
import ChatSessionPage from '@/pages/user/projects/ChatSessionPage';
import ProjectSettingsPage from '@/pages/user/projects/ProjectSettingsPage';
import ToolListPage from '@/pages/user/projects/ToolListPage';
import ProjectIndexPage from '@/pages/user/projects/ProjectIndexPage';
import PlanFeedbackPreviewPage from '@/pages/dev/PlanFeedbackPreviewPage';
import type { RouteObject } from 'react-router-dom';

const routes: RouteObject[] = [
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <UserLayout />,
        children: [
          {
            path: '',
            element: <ProjectListPage />,
          },
        ],
      },
      {
        path: '/projects/:projectId',
        element: <ProjectLayout />,
        children: [
          {
            index: true,
            element: <ProjectIndexPage />,
          },
          {
            path: 'sessions',
            element: <div className="p-8 text-slate-500 h-full flex items-center justify-center">좌측 메뉴에서 대화 세션을 선택하거나 '새 대화'를 시작하세요.</div>,
          },
          {
            path: 'sessions/:sessionId',
            element: <ChatSessionPage />,
          },
          {
            path: 'tools',
            element: <ToolListPage />,
          },
          {
            path: 'settings',
            element: <ProjectSettingsPage />,
          },
        ],
      },
      {
        path: '/admin',
        element: <AdminLayout />,
        children: [
          {
            path: '',
            element: <SuperAdminPage />,
          },
        ],
      },
    ],
  },
  {
    path: '/login',
    element: <AuthLayout />,
    children: [
      {
        path: '',
        element: <LoginPage />,
      },
    ],
  },
];

if (import.meta.env.DEV) {
  routes.push({
    path: '/dev/plan-feedback',
    element: <PlanFeedbackPreviewPage />,
  });
}

export const router = createBrowserRouter(routes);
