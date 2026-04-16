import React, { memo } from 'react';
import { Link } from 'react-router-dom';
import { StockLogo } from './StockLogo';
import { Heart } from 'lucide-react';
import { useStockStore } from '../../store/useStockStore';
import { useAuthStore } from '../../store/useAuthStore';

export interface StockRowProps {
    ticker: string;
    rank: number;
    name: string;
    currentPrice: number;
    changeRate: number;
    accVolume: number;
}

const formatTradeAmount = (value: number) => {
    if (value >= 1000000000000) {
        return `${(value / 1000000000000).toFixed(1).replace('.0', '')}조`;
    }
    if (value >= 100000000) {
        return `${Math.floor(value / 100000000).toLocaleString()}억`;
    }
    if (value >= 10000) {
        return `${Math.floor(value / 10000).toLocaleString()}만`;
    }
    return `${value.toLocaleString()}`;
};

const StockRow: React.FC<StockRowProps> = ({
    ticker,
    rank,
    name,
    currentPrice,
    changeRate,
    accVolume,
}) => {
    const isPositive = changeRate > 0;
    const changeColor = isPositive ? 'text-[#e84c3d]' : 'text-[#2b7fff]';
    const changeSign = isPositive ? '+' : '';

    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const isFavorite = useStockStore(state => state.watchlist.has(ticker));
    const toggleWatchlist = useStockStore(state => state.toggleWatchlist);

    const handleHeartClick = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (isLoggedIn) {
            toggleWatchlist(ticker);
        } else {
            alert('로그인이 필요한 기능입니다.');
        }
    };

    return (
        <Link to={`/stock/${ticker}`} className="bg-transparent flex h-[55px] items-center px-[18px] w-full min-w-[776px]">
            {/* Watchlist & Rank */}
            <div className="w-[60px] shrink-0 flex items-center gap-5 mr-2">
                <button
                    onClick={handleHeartClick}
                    className={`transition-colors hover:scale-110 active:scale-95 ${isFavorite ? 'text-red-500' : 'text-slate-200 hover:text-red-400'}`}
                >
                    <Heart size={16} fill="currentColor" strokeWidth={0} />
                </button>
                <span className="text-[16px] text-black font-normal">{rank}</span>
            </div>

            {/* Name and Icon */}
            <div className="flex items-center gap-[10px] w-[220px] shrink-0">
                <StockLogo ticker={ticker} name={name} className="size-[30px] rounded-full" fallbackClassName="text-[11px] text-white font-bold" />
                <span className="text-[16px] text-black font-normal truncate">{name}</span>
            </div>

            {/* Flexible shrinking spacer */}
            <div className="flex-1 min-w-[10px] max-w-[120px]"></div>

            {/* Price */}
            <div className="w-[110px] shrink-0 text-right">
                <span className="text-[16px] text-black font-normal">
                    {currentPrice.toLocaleString()}원
                </span>
            </div>

            {/* Flexible shrinking spacer */}
            <div className="flex-1 min-w-[10px] max-w-[120px]"></div>

            {/* Change Rate */}
            <div className="w-[110px] shrink-0 text-right">
                <span className={`text-[16px] font-normal ${changeColor}`}>
                    {changeSign}{changeRate.toFixed(2)}%
                </span>
            </div>

            {/* Flexible shrinking spacer */}
            <div className="flex-1 min-w-[10px] max-w-[120px]"></div>

            {/* Volume */}
            <div className="w-[130px] shrink-0 text-right">
                <span className="text-[16px] text-black font-normal">
                    {formatTradeAmount(accVolume * currentPrice)}원
                </span>
            </div>

        </Link>
    );
};

export default memo(StockRow, (prev, next) => {
    // 가격, 등락률, 순위, 거래량, 매수/매도 비율이 모두 동일하면 리렌더링 방지
    return (
        prev.currentPrice === next.currentPrice &&
        prev.changeRate === next.changeRate &&
        prev.rank === next.rank &&
        prev.accVolume === next.accVolume
    );
});
