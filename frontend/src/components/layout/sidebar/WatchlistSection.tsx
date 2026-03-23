import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAccountStore } from "../../../store/useAccountStore";
import { useAuthStore } from "../../../store/useAuthStore";
import { useStockStore } from "../../../store/useStockStore";
import { useMarketStore } from "../../../store/useMarketStore";
import { ScrollArea } from "../../ui/scroll-area";
import { StockLogo } from "../../stock/StockLogo";
import { useEffect } from "react";

export function WatchlistSection() {
    const navigate = useNavigate();
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const { watchlist, fetchWatchlist } = useStockStore();
    const stocksMap = useMarketStore(state => state.stocks);

    useEffect(() => {
        if (isLoggedIn) {
            fetchWatchlist();
        }
    }, [isLoggedIn, fetchWatchlist]);

    // 관심 종목 리스트 생성 (마켓 스토어의 실시간 데이터 결합)
    const watchlistItems = Array.from(watchlist).map(ticker => {
        const marketData = stocksMap[ticker];
        return {
            ticker,
            name: marketData?.name || ticker,
            currentPrice: marketData?.currentPrice || 0,
            changeRate: marketData?.changeRate || 0,
        };
    });

    return (
        <div className="flex flex-col h-full w-[320px] min-w-[320px] bg-white">
            <div className="p-6 border-b border-slate-100">
                <div className="flex items-center justify-between mb-2">
                    <h2 className="text-lg font-bold text-slate-800">관심 종목</h2>
                </div>
            </div>

            {!isLoggedIn ? (
                <div className="flex-1 flex items-center justify-center p-10 text-center">
                    <div>
                        <p className="text-slate-400 text-sm mb-1">로그인이 필요한 서비스입니다.</p>
                        <p className="text-slate-300 text-[11px]">관심 종목을 등록하고 관리해 보세요.</p>
                    </div>
                </div>
            ) : (
                <ScrollArea className="flex-1">
                    <div className="py-2">
                        <div className="px-6 mb-2">
                            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">전체 {watchlistItems.length}</span>
                        </div>

                        <div className="flex flex-col">
                            {watchlistItems.length === 0 ? (
                                <div className="py-20 text-center px-10">
                                    <p className="text-slate-400 text-sm mb-1">등록된 관심 종목이 없습니다.</p>
                                    <p className="text-slate-300 text-[11px]">종목 리스트의 하트를 눌러보세요.</p>
                                </div>
                            ) : (
                                watchlistItems.map((item) => {
                                    const isPositive = item.changeRate > 0;
                                    const color = isPositive ? 'text-red-500' : item.changeRate < 0 ? 'text-blue-500' : 'text-slate-500';

                                    return (
                                        <div 
                                            key={item.ticker} 
                                            onClick={() => navigate(`/stock/${item.ticker}`)}
                                            className="px-4 py-3.5 hover:bg-slate-50 transition-all cursor-pointer group border-b border-transparent hover:border-slate-100"
                                        >
                                            <div className="flex justify-between items-center gap-2">
                                                {/* 왼쪽: 로고 및 종목명 */}
                                                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                                                    <StockLogo ticker={item.ticker} name={item.name} className="w-8 h-8 rounded-full border border-slate-50 shrink-0" />
                                                    <div className="flex flex-col gap-0.5 min-w-0">
                                                        <h3 className="font-bold text-sm text-slate-800 group-hover:text-blue-600 transition-colors truncate">{item.name}</h3>
                                                        <p className="text-[10px] text-slate-400 font-medium uppercase tracking-tight">{item.ticker}</p>
                                                    </div>
                                                </div>

                                                {/* 오른쪽: 가격 및 등락률 */}
                                                <div className="flex flex-col items-end gap-0.5 shrink-0">
                                                    <p className="text-sm font-bold text-slate-800 whitespace-nowrap">{item.currentPrice.toLocaleString()}원</p>
                                                    <div className={`flex items-center text-[10px] font-bold ${color} whitespace-nowrap`}>
                                                        {item.changeRate > 0 ? <TrendingUp className="w-2.5 h-2.5 mr-0.5" /> : item.changeRate < 0 ? <TrendingDown className="w-2.5 h-2.5 mr-0.5" /> : <Minus className="w-2.5 h-2.5 mr-0.5" />}
                                                        <span>{isPositive ? '+' : ''}{item.changeRate.toFixed(2)}%</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>                                    );
                                })
                            )}
                        </div>
                    </div>
                </ScrollArea>
            )}
        </div>
    );
}
