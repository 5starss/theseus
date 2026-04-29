import { Outlet } from 'react-router-dom';

export default function AuthLayout() {
  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[#051424] relative overflow-hidden">
      {/* Main content container */}
      <div className="relative z-10 w-full p-4 flex justify-center">
        <Outlet />
      </div>
    </div>
  );
}
