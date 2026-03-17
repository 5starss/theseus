import { useState, useEffect, useRef } from "react";
import { ChevronsLeft, ChevronsRight, Wallet, Bot, TrendingUp, TrendingDown, Minus, Sparkles } from "lucide-react";
import { useAccountStore } from "../../store/useAccountStore";
import { useAuthStore } from "../../store/useAuthStore";

type SidebarMenu = 'HOLDINGS' | 'AI' | null;

export default function Sidebar() {
    const [isExpanded, setIsExpanded] = useState(false);
    const [activeMenu, setActiveMenu] = useState<SidebarMenu>(null);
    const sidebarRef = useRef<HTMLDivElement>(null);

    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const {
        cashBalance,
        totalInvested,
        totalEvaluated,
        portfolio,
        fetchBalance,
        fetchPositions
    } = useAccountStore();

    // 사이드바가 열리거나 로그인 상태가 변할 때 데이터 최신화
    useEffect(() => {
        if (isExpanded && isLoggedIn) {
            fetchBalance();
            fetchPositions();
        }
    }, [isExpanded, isLoggedIn, fetchBalance, fetchPositions]);

    const toggleExpand = () => {
        setIsExpanded(!isExpanded);
        if (isExpanded) setActiveMenu(null);
    };

    const handleMenuClick = (menu: SidebarMenu) => {
        if (activeMenu === menu) {
            setIsExpanded(false);
            setActiveMenu(null);
        } else {
            setIsExpanded(true);
            setActiveMenu(menu);
        }
    };

    const totalProfit = totalEvaluated - totalInvested;
    const profitRate = totalInvested > 0 ? (totalProfit / totalInvested) * 100 : 0;
    const profitColor = totalProfit > 0 ? 'text-red-500' : totalProfit < 0 ? 'text-blue-500' : 'text-slate-500';

    return (
        <aside
            ref={sidebarRef}
            className={`h-full flex transition-all duration-300 ease-in-out shrink-0 z-50 relative overflow-visible
                ${isExpanded ? 'w-0 xl:w-96' : 'w-0 xl:w-16'}
            `}
        >
            {/* Right: Content Area (Opened to the LEFT of the icon bar) */}
            <div className={`flex flex-col h-full bg-white overflow-hidden transition-all duration-300 absolute right-16 border-l border-slate-100 shadow-[-8px_0_24px_rgba(0,0,0,0.06)]
                ${isExpanded ? 'opacity-100 w-[320px] xl:relative xl:right-0 xl:shadow-none' : 'opacity-0 w-0 pointer-events-none'}
            `}>
                {activeMenu === 'HOLDINGS' && (
                    <div className="flex flex-col h-full w-[320px]">
                        <div className="p-6 border-b border-slate-100">
                            <h2 className="text-lg font-bold text-slate-800 mb-6">내 주식</h2>

                            {!isLoggedIn ? (
                                <div className="py-10 text-center">
                                    <p className="text-slate-400 text-sm">로그인이 필요한 서비스입니다.</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div>
                                        <p className="text-xs text-slate-400 font-medium mb-1">주문 가능 금액</p>
                                        <p className="text-xl font-bold text-slate-800">{cashBalance.toLocaleString()}원</p>
                                    </div>
                                    <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                                        <p className="text-xs text-slate-400 font-medium mb-1">총 투자 금액</p>
                                        <div className="flex items-baseline gap-2">
                                            <p className="text-lg font-bold text-slate-800">{totalInvested.toLocaleString()}원</p>
                                            <div className={`flex items-center text-xs font-bold ${profitColor}`}>
                                                {totalProfit > 0 ? <TrendingUp className="w-3 h-3 mr-0.5" /> : totalProfit < 0 ? <TrendingDown className="w-3 h-3 mr-0.5" /> : <Minus className="w-3 h-3 mr-0.5" />}
                                                {Math.abs(totalProfit).toLocaleString()}원 ({profitRate >= 0 ? '+' : ''}{profitRate.toFixed(2)}%)
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="flex-1 overflow-y-auto px-6 py-4">
                            <div className="flex items-center justify-between mb-4">
                                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">보유 주식 {portfolio.length}</span>
                            </div>

                            <div className="space-y-3">
                                {portfolio.length === 0 ? (
                                    <p className="text-center py-10 text-slate-400 text-sm">보유하신 주식이 없습니다.</p>
                                ) : (
                                    portfolio.map((item) => {
                                        const profit = (item.currentPrice - item.avgPrice) * item.shares;
                                        const rate = ((item.currentPrice - item.avgPrice) / item.avgPrice) * 100;
                                        const color = profit > 0 ? 'text-red-500' : profit < 0 ? 'text-blue-500' : 'text-slate-500';

                                        return (
                                            <div key={item.code} className="p-4 rounded-xl border border-slate-100 hover:border-blue-200 hover:bg-blue-50/30 transition-all cursor-pointer group">
                                                <div className="flex justify-between items-start mb-2">
                                                    <div>
                                                        <h3 className="font-bold text-slate-800 group-hover:text-blue-600 transition-colors">{item.name}</h3>
                                                        <p className="text-[10px] text-slate-400 font-medium">{item.code}</p>
                                                    </div>
                                                    <div className="text-right">
                                                        <p className="font-bold text-slate-800">{(item.currentPrice * item.shares).toLocaleString()}원</p>
                                                        <p className="text-[10px] text-slate-400">{item.shares}주</p>
                                                    </div>
                                                </div>
                                                <div className="flex justify-between items-center text-xs font-bold">
                                                    <span className="text-slate-400 font-medium">수익률</span>
                                                    <span className={color}>
                                                        {profit >= 0 ? '+' : ''}{rate.toFixed(2)}%
                                                    </span>
                                                </div>
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {activeMenu === 'AI' && (
                    <div className="flex flex-col h-full p-6 w-[320px]">
                        <h2 className="text-lg font-bold text-slate-800 mb-6">AI 분석</h2>
                        <div className="flex-1 flex flex-col items-center justify-center text-center space-y-4">
                            <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center text-blue-600 animate-pulse">
                                <Sparkles className="w-8 h-8" />
                            </div>
                            <p className="text-slate-400 text-sm leading-relaxed">
                                AI가 종목 정보를 분석하고 있습니다.<br />잠시만 기다려 주세요.
                            </p>
                        </div>
                    </div>
                )}
            </div>

            {/* Left: Icon Bar (Positioned on the RIGHT now) */}
            <div className="w-16 h-full bg-slate-50 flex flex-col items-center py-4 gap-6 border-l border-slate-100 absolute right-0 xl:static xl:right-auto z-20 shadow-[-8px_0_24px_rgba(0,0,0,0.06)] xl:shadow-none">
                <button
                    onClick={toggleExpand}
                    className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all cursor-pointer group"
                    title={isExpanded ? "사이드바 접기" : "사이드바 펼치기"}
                >
                    {isExpanded ? (
                        <ChevronsRight className="w-6 h-6" />
                    ) : (
                        <ChevronsLeft className="w-6 h-6 group-hover:-translate-x-0.5 transition-transform" />
                    )}
                </button>

                <div className="w-8 h-[1px] bg-slate-200"></div>

                <button
                    onClick={() => handleMenuClick('HOLDINGS')}
                    className={`p-2 rounded-xl transition-all cursor-pointer flex flex-col items-center gap-1 group ${activeMenu === 'HOLDINGS' ? 'text-blue-600 bg-blue-50' : 'text-slate-500 hover:text-blue-600 hover:bg-blue-50'}`}
                    title="보유 종목"
                >
                    <Wallet className="w-6 h-6 group-hover:scale-110 transition-transform" />
                    <span className="text-[10px] font-bold shrink-0">내 주식</span>
                </button>

                <button
                    onClick={() => handleMenuClick('AI')}
                    className={`p-2 rounded-xl transition-all cursor-pointer flex flex-col items-center gap-1 group ${activeMenu === 'AI' ? 'text-blue-600 bg-blue-50' : 'text-slate-500 hover:text-blue-600 hover:bg-blue-50'}`}
                    title="AI 분석"
                >
                    <Bot className="w-6 h-6 group-hover:scale-110 transition-transform" />
                    <span className="text-[10px] font-bold shrink-0">AI</span>
                </button>
            </div>
        </aside>
    );
}
