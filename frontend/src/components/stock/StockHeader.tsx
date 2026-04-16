import { useStockStore } from "../../store/useStockStore";
import { useAuthStore } from "../../store/useAuthStore";
import { StockLogo } from "./StockLogo";
import { Heart } from "lucide-react";

export function StockHeader() {
    const { stockCode, stockName, currentPrice, priceChange, changeRate, watchlist, toggleWatchlist } = useStockStore();
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const isFavorite = watchlist.has(stockCode);

    const isPositive = priceChange > 0;
    const isNegative = priceChange < 0;
    const colorClass = isPositive ? 'text-red-500' : isNegative ? 'text-blue-500' : 'text-slate-800';
    const sign = isPositive ? '▲' : isNegative ? '▼' : '-';
    const plusSign = isPositive ? '+' : '';

    const handleHeartClick = () => {
        if (isLoggedIn) {
            toggleWatchlist(stockCode);
        } else {
            alert('로그인이 필요한 기능입니다.');
        }
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex items-center gap-8">
            <div className="flex items-center gap-3">
                <StockLogo ticker={stockCode} name={stockName} className="w-12 h-12 rounded-lg" fallbackClassName="text-white font-bold" />
                <div>
                    <h1 className="text-xl font-bold text-slate-800 leading-tight">{stockName}</h1>
                    <span className="text-xs text-slate-500 font-medium">{stockCode}</span>
                </div>
            </div>

            <div className="w-px h-8 bg-slate-200 block"></div>

            <div className="flex flex-col">
                <div className="flex items-baseline gap-2">
                    <span className={`text-2xl font-bold ${colorClass} leading-none`}>
                        {currentPrice.toLocaleString()}
                    </span>
                    <span className={`text-sm font-semibold ${colorClass} tracking-tight`}>
                        {sign} {Math.abs(priceChange).toLocaleString()} ({plusSign}{changeRate.toFixed(2)}%)
                    </span>
                </div>
            </div>

            {/* 관심 종목 하트 버튼 */}
            <button
                onClick={handleHeartClick}
                className={`ml-auto p-2.5 rounded-xl border transition-all active:scale-95 flex items-center justify-center ${
                    isFavorite 
                    ? 'bg-red-50 border-red-100 text-red-500 hover:bg-red-100' 
                    : 'bg-slate-50 border-slate-100 text-slate-300 hover:bg-slate-100 hover:text-red-400'
                }`}
            >
                <Heart size={22} fill="currentColor" strokeWidth={0} />
            </button>
        </div>
    );
}

