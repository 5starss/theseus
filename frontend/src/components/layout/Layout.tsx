import { Outlet } from "react-router-dom";
import Header from "./Header.tsx";

export default function Layout() {
    return (
        <div className="flex flex-col h-screen min-h-screen bg-slate-100 font-sans text-slate-900 overflow-hidden">
            {/* 내비게이션 바 */}
            <Header />

            {/* 메인 컨텐츠(너비 최대로) */}
            <main className="flex-1 w-full flex overflow-hidden">
                <Outlet />
            </main>
        </div>
    );
}
