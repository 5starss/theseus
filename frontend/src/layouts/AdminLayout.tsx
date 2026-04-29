import { Outlet } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useAuthStore } from '../store/useAuthStore';
import { useNavigate } from 'react-router-dom';

export default function AdminLayout() {
  const { logout, user } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Top App Bar */}
      <header className="h-16 border-b border-white/10 bg-[#051424] flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-2">
          {/* Logo or Title */}
          <h1 className="text-xl font-semibold text-white tracking-wide">
            Theseus <span className="text-white/60 font-medium">Admin</span>
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
      <main className="flex-1 overflow-auto bg-[#051424]">
        <div className="mx-auto pt-[30px] pb-10 w-[1302px]">
          <div className="mb-[40px]">
            <h2 className="text-[32px] font-medium text-[#d4e4fa] tracking-[-0.8px]">관리자 페이지</h2>
          </div>

          <Outlet />
        </div>
      </main>
    </div>
  );
}
