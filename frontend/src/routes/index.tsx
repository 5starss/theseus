import { createBrowserRouter } from 'react-router-dom';
import AuthLayout from '@/layouts/AuthLayout';
import LoginPage from '@/pages/auth/LoginPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AuthLayout />,
    children: [
      {
        path: '',
        element: <LoginPage />, // temporarily redirect root to login
      },
      {
        path: 'login',
        element: <LoginPage />,
      },
    ],
  },
]);
