import { Outlet } from "react-router-dom";
import Header from "./Header.tsx";
import Sidebar from "./Sidebar.tsx";

export default function Layout() {
    return (
        <div className="flex flex-col h-screen min-h-screen bg-slate-100 font-sans text-slate-900 overflow-hidden">
            {/* 내비게이션 바 */}
            <Header />

            <div className="flex-1 flex overflow-hidden min-h-0 relative">
                {/* 메인 컨텐츠 */}
                <main className="flex-1 flex flex-col overflow-auto min-h-0">
                    <Outlet />
                </main>

                {/* 우측 사이드바 */}
                <Sidebar />
            </div>
        </div>
    );
}
