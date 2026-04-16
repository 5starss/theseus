import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';

export default function ProtectedRoute() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const location = useLocation();

    if (!isLoggedIn) {
        // 로그인 페이지로 이동하고, 현재 위치를 저장하여 로그인 후 다시 돌아갈 수 있도록 함
        // replace: 현재 페이지를 history에 저장하지 않음
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return <Outlet />;
}
