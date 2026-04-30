import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/store/useAuthStore';

interface ProtectedRouteProps {
  allowedRoles?: ('SUPER_ADMIN' | 'USER')[];
}

const ProtectedRoute = ({ allowedRoles }: ProtectedRouteProps) => {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.systemRole)) {
    // 권한이 없는 경우 메인 페이지로 리다이렉트
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
