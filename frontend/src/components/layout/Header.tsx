import { SearchIcon } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

export default function Header() {
    const location = useLocation();

    // 네비게이션 활성화 도우미 (단순한 문자열 포함 검사)
    const isActive = (path: string) => {
        if (path === '/' && location.pathname === '/') return true;
        if (path !== '/' && location.pathname.startsWith(path)) return true;
        return false;
    };

    return (
        <header className="h-14 w-full bg-white border-b border-slate-200 flex items-center px-4 shrink-0 shadow-sm z-10">

            {/* 왼쪽: 로고, 내비게이션 */}
            <div className="flex items-center h-full mr-4">
                <Link to="/" className="flex items-center gap-2 mr-6">
                    <div className="w-7 h-7 bg-blue-600 text-white flex items-center justify-center font-bold rounded">
                        S
                    </div>
                    <span className="font-bold text-lg tracking-tight">싸피증권</span>
                </Link>

                <div className="w-px h-6 bg-slate-300 mx-2"></div>

                <nav className="flex items-center h-full ml-2 space-x-1">
                    <Link
                        to="/"
                        className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors text-sm ${isActive('/') ? 'text-blue-600 bg-blue-50/50 font-semibold' : 'text-slate-600 hover:bg-slate-50 hover:text-blue-600 font-medium'}`}
                    >
                        홈
                    </Link>
                    <p className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors text-sm ${isActive('/stock') ? 'text-blue-600 bg-blue-50/50 font-semibold' : 'text-slate-600 cursor-default font-medium'}`}>
                        주식
                    </p>
                    <Link
                        to="/"
                        className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors text-sm ${isActive('/account') ? 'text-blue-600 bg-blue-50/50 font-semibold' : 'text-slate-600 hover:bg-slate-50 hover:text-blue-600 font-medium'}`}
                    >
                        내 계좌
                    </Link>
                </nav>
            </div>

            {/* 가운데: 코스피, 코스닥(더미) */}
            <div className="hidden lg:flex items-center gap-6">
                <div className="flex flex-col">
                    <span className="text-[10px] text-slate-500 font-semibold mb-0.5">KOSPI</span>
                    <div className="flex items-baseline gap-2">
                        <span className="text-sm font-bold text-red-500">2,650.45</span>
                        <span className="text-xs font-semibold text-red-500">▲ 0.46%</span>
                    </div>
                </div>
                <div className="flex flex-col"> 
                    <span className="text-[10px] text-slate-500 font-semibold mb-0.5">KOSDAQ</span>
                    <div className="flex items-baseline gap-2">
                        <span className="text-sm font-bold text-blue-500">850.12</span>
                        <span className="text-xs font-semibold text-blue-500">▼ 0.52%</span>
                    </div>
                </div>
            </div>

            {/* 오른쪽: 검색, 로그인 */}
            <div className="flex items-center gap-4 ml-auto">
                <div className="relative hidden md:block">
                    <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                        type="text"
                        placeholder="메뉴, 종목 검색"
                        className="h-8 pl-9 pr-4 w-52 bg-slate-100 rounded-full text-sm outline-none focus:ring-2 focus:ring-blue-500/20 focus:bg-white transition-all"
                    />
                </div>
                <div className="w-px h-6 bg-slate-300 mx-2 hidden md:block"></div>
                <div className="flex items-center">
                    <Link to="/" className="px-4 py-1.5 bg-[#155dfc] hover:bg-[#124bc9] text-white text-sm font-bold rounded-md transition-colors shadow-sm">
                        로그인
                    </Link>
                </div>
            </div>
        </header>
    );
}
