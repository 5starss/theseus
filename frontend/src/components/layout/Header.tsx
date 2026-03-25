import { SearchIcon, LogOutIcon, UserIcon } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "../../store/useAuthStore";
import { authApi } from "../../api/auth";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useState, useEffect, useRef } from "react";
import { stockApi, type Stock } from "../../api/stock";
import { Skeleton } from "@/components/ui/skeleton";

export default function Header() {
    const location = useLocation();
    const navigate = useNavigate();
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const user = useAuthStore(state => state.user);
    const logout = useAuthStore(state => state.logout);

    // 검색 관련 상태
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<Stock[]>([]);
    const [showResults, setShowResults] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const searchRef = useRef<HTMLDivElement>(null);

    // 검색 로직 (Debounce)
    useEffect(() => {
        if (searchQuery.trim().length === 0) {
            setSearchResults([]);
            setShowResults(false);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setShowResults(true);

        const timer = setTimeout(async () => {
            try {
                const results = await stockApi.searchStocks(searchQuery);
                setSearchResults(results);
            } finally {
                setIsLoading(false);
            }
        }, 150); // 300ms -> 150ms로 단축

        return () => clearTimeout(timer);
    }, [searchQuery]);

    // 외부 클릭 시 검색 결과 닫기
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
                setShowResults(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // 네비게이션 활성화 도우미 (단순한 문자열 포함 검사)
    const isActive = (path: string) => {
        if (path === '/' && location.pathname === '/') return true;
        if (path !== '/' && location.pathname.startsWith(path)) return true;
        return false;
    };

    const handleResultClick = (ticker: string) => {
        navigate(`/stock/${ticker}`);
        setSearchQuery("");
        setShowResults(false);
    };

    return (
        <header className="h-14 w-full bg-white border-b border-slate-200 flex items-center px-4 shrink-0 shadow-sm z-50">

            {/* 왼쪽: 로고, 내비게이션 */}
            <div className="flex items-center h-full mr-4">
                <Link to="/" className="flex items-center gap-2 mr-6">
                    <img src="/Logo.png" alt="Logo" className="w-7 h-7" />
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
                        to="/ranking"
                        className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors text-sm ${isActive('/ranking') ? 'text-blue-600 bg-blue-50/50 font-semibold' : 'text-slate-600 hover:bg-slate-50 hover:text-blue-600 font-medium'}`}
                    >
                        랭킹
                    </Link>
                    <Link
                        to="/account"
                        className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors text-sm ${isActive('/account') ? 'text-blue-600 bg-blue-50/50 font-semibold' : 'text-slate-600 hover:bg-slate-50 hover:text-blue-600 font-medium'}`}
                    >
                        내 계좌
                    </Link>
                </nav>
            </div>

            {/* 가운데: 코스피, 코스닥 영역이 제거됨 */}

            {/* 오른쪽: 검색, 로그인 */}
            <div className="flex items-center ml-auto gap-4">
                <div className="relative hidden md:block" ref={searchRef}>
                    <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                        type="text"
                        placeholder="종목 검색"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onFocus={() => searchQuery.length > 0 && setShowResults(true)}
                        className="h-8 pl-9 pr-4 w-52 bg-slate-100 rounded-full text-sm outline-none focus:ring-2 focus:ring-blue-500/20 focus:bg-white transition-all"
                    />

                    {/* 검색 결과 드롭다운 */}
                    {showResults && (
                        <div className="absolute top-full mt-2 left-0 w-64 bg-white border border-slate-100 rounded-xl shadow-2xl py-2 overflow-hidden z-50">
                            {isLoading ? (
                                <div className="px-1 py-1 flex flex-col gap-1">
                                    <p className="px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">검색 결과</p>
                                    {[1, 2, 3].map((i) => (
                                        <div key={i} className="px-4 py-2.5 flex justify-between items-center">
                                            <div className="flex items-center gap-3">
                                                <Skeleton className="w-8 h-8 rounded-full" />
                                                <div className="flex flex-col gap-1.5">
                                                    <Skeleton className="w-20 h-3.5" />
                                                    <Skeleton className="w-12 h-2.5" />
                                                </div>
                                            </div>
                                            <div className="flex flex-col items-end gap-1.5">
                                                <Skeleton className="w-16 h-3" />
                                                <Skeleton className="w-10 h-2.5" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : searchResults.length > 0 ? (
                                <div className="max-h-[320px] overflow-y-auto">
                                    <p className="px-4 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">검색 결과</p>
                                    {searchResults.map((stock) => (
                                        <div
                                            key={stock.ticker}
                                            onClick={() => handleResultClick(stock.ticker)}
                                            className="px-4 py-2.5 hover:bg-slate-50 cursor-pointer flex justify-between items-center transition-colors group"
                                        >
                                            <div className="flex items-center gap-3">
                                                {/* 종목 로고 */}
                                                <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center overflow-hidden shrink-0 border border-slate-50">
                                                    <img
                                                        src={`/icons/stocks/${stock.ticker}.png`}
                                                        alt={stock.name}
                                                        className="w-full h-full object-cover"
                                                        onError={(e) => {
                                                            (e.target as HTMLImageElement).style.display = 'none';
                                                            const parent = (e.target as HTMLImageElement).parentElement;
                                                            if (parent && !parent.querySelector('.fallback-text')) {
                                                                const span = document.createElement('span');
                                                                span.className = 'fallback-text text-[10px] font-bold text-slate-400';
                                                                span.innerText = stock.name.charAt(0);
                                                                parent.appendChild(span);
                                                            }
                                                        }}
                                                    />
                                                </div>
                                                <div className="flex flex-col gap-0.5">
                                                    <span className="text-sm font-bold text-slate-700 group-hover:text-blue-600">{stock.name}</span>
                                                    <span className="text-[11px] text-slate-400 font-medium tracking-tight">{stock.ticker}</span>
                                                </div>
                                            </div>
                                            <div className="flex flex-col items-end">
                                                <span className="text-xs font-bold text-slate-700">{stock.currentPrice.toLocaleString()}원</span>
                                                <span className={`text-[10px] font-bold ${stock.changeRate >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                                                    {stock.changeRate >= 0 ? '+' : ''}{stock.changeRate}%
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="px-4 py-6 text-center">
                                    <p className="text-sm text-slate-400 font-medium">검색 결과가 없습니다.</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
                <div className="w-px h-6 bg-slate-300 mx-2 hidden md:block"></div>

                {/* 사용자 메뉴 */}
                {/* 로그인 상태: 내 정보 드롭다운 */}
                {/* 로그아웃 상태: 로그인 버튼 */}
                {isLoggedIn ? (
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <button className="flex items-center gap-2 px-2 py-1.5 rounded-full bg-slate-50 hover:bg-slate-100 transition-all outline-none">
                                <div className="w-8 h-8 bg-slate-200 text-slate-600 flex items-center justify-center font-bold rounded-full text-sm shrink-0">
                                    {user?.name ? user.name.charAt(0) : 'K'}
                                </div>
                                <span className="text-[14px] font-bold text-slate-700 hidden sm:block">{user?.name}</span>
                            </button>
                        </DropdownMenuTrigger>

                        <DropdownMenuContent align="end" className="w-[240px] rounded-2xl shadow-[0px_10px_40px_0px_rgba(0,0,0,0.08)] py-2 border-slate-100">
                            <div className="px-5 py-3 mb-1">
                                <p className="text-[15px] font-bold text-slate-800">{user?.name}</p>
                                <p className="text-[13px] text-slate-500 mt-0.5">{user?.email}</p>
                            </div>
                            <DropdownMenuSeparator className="bg-slate-100 mx-2 mb-2" />
                            <div className="px-2 font-medium">
                                <DropdownMenuItem asChild className="gap-3 px-3 py-2.5 text-[14px] text-slate-700 hover:bg-slate-50 rounded-xl cursor-pointer">
                                    <Link to="/mypage">
                                        <UserIcon className="w-4 h-4 text-slate-400" />
                                        내 정보
                                    </Link>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={async () => {
                                        try {
                                            await authApi.logout();
                                        } catch (error) {
                                            console.error("Logout failed:", error);
                                        } finally {
                                            logout();
                                            window.location.href = '/';  // 로그아웃 시 홈으로 이동
                                        }
                                    }}
                                    className="gap-3 px-3 py-2.5 text-[14px] text-red-600 focus:text-red-600 focus:bg-red-50 rounded-xl cursor-pointer mt-1"
                                >
                                    <LogOutIcon className="w-4 h-4 text-red-500" />
                                    로그아웃
                                </DropdownMenuItem>
                            </div>
                        </DropdownMenuContent>
                    </DropdownMenu>
                ) : (
                    <div className="flex items-center">
                        <Button asChild className="px-4 py-1.5 bg-[#155dfc] hover:bg-[#124bc9] text-white text-sm font-bold rounded-md transition-colors shadow-sm h-8">
                            <Link to="/login" state={{ from: location }}>
                                로그인
                            </Link>
                        </Button>
                    </div>
                )}
            </div>
        </header>
    );
}
