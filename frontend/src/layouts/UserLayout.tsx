import { Outlet, useNavigate } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';
import { authApi } from '@/api/auth';

export default function UserLayout() {
  const { logout, user } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout API failed:', error);
    } finally {
      logout();
      navigate('/login');
    }
  };

  return (
    <div className="min-h-screen bg-[#010f1f] text-foreground flex flex-col relative overflow-hidden">
      {/* Top App Bar */}
      <header className="h-16 border-b border-white/10 bg-[rgba(5,20,36,0.8)] backdrop-blur-md flex items-center justify-between px-6 shrink-0 relative z-10">
        <div className="flex items-center gap-2">
          {/* Logo or Title */}
          <h1 className="text-xl font-semibold text-white tracking-wide cursor-pointer" onClick={() => navigate('/')}>
            Theseus
          </h1>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-sm text-white/80">{user?.name} 님</span>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-white/60 hover:text-white transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>로그아웃</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-auto relative z-10">
        <Outlet />
      </main>
    </div>
  );
}
