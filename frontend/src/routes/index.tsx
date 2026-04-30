import { createBrowserRouter } from 'react-router-dom';
import AuthLayout from '@/layouts/AuthLayout';
import LoginPage from '@/pages/auth/LoginPage';
import AdminLayout from '@/layouts/AdminLayout';
import SuperAdminPage from '@/pages/admin/SuperAdminPage';
import UserLayout from '@/layouts/UserLayout';
import ProjectListPage from '@/pages/user/ProjectListPage';
import ProtectedRoute from './ProtectedRoute';

export const router = createBrowserRouter([
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
]);
