import React, { memo } from 'react';
import { Link } from 'react-router-dom';

export interface StockRowProps {
    code: string;
    rank: number;
    name: string;
    price: number;
    changeRate: number;
    volume: number; // 단위: 억
    buyRatio: number;
    sellRatio: number;
}

const getStockIcon = (name: string) => {
    // 종목명 길이에 따라 아이콘 색상 결정 (간단한 해시 함수)
    const colors = [
        'bg-[#155dfc]',
        'bg-[#fb2c36]',
        'bg-[#2b7fff]',
        'bg-[#101828]',
        'bg-[#6a7282]',
    ];
    return colors[name.length % colors.length];
};

const StockRow: React.FC<StockRowProps> = ({
    code,
    rank,
    name,
    price,
    changeRate,
    volume,
    buyRatio,
    sellRatio,
}) => {
    const isPositive = changeRate > 0;
    const changeColor = isPositive ? 'text-[#e84c3d]' : 'text-[#2b7fff]';
    const changeSign = isPositive ? '+' : '';

    return (
        <Link to={`/stock/${code}`} className="bg-transparent flex h-[55px] items-center justify-between px-[18px] w-full shrink-0 block">
            {/* Rank */}
            <div className="w-[60px] shrink-0">
                <span className="text-[16px] text-black font-normal">{rank}</span>
            </div>

            {/* Name and Icon */}
            <div className="flex items-center gap-[10px] w-[311px] shrink-0">
                <div className={`rounded-full size-[26px] shrink-0 ${getStockIcon(name)}`}></div>
                <span className="text-[16px] text-black font-normal">{name}</span>
            </div>

            {/* Price */}
            <div className="w-[120px] shrink-0 text-right">
                <span className="text-[16px] text-black font-normal">
                    {price.toLocaleString()}원
                </span>
            </div>

            {/* Change Rate */}
            <div className="w-[120px] shrink-0 text-right">
                <span className={`text-[16px] font-normal ${changeColor}`}>
                    {changeSign}{changeRate.toFixed(2)}%
                </span>
            </div>

            {/* Space for layout matching Figma */}
            <div className="w-[60px] shrink-0"></div>

            {/* Volume */}
            <div className="w-[194px] shrink-0">
                <span className="text-[16px] text-black font-normal">{volume.toLocaleString()}억</span>
            </div>

            {/* Space for layout matching Figma */}
            <div className="flex-1 shrink-0"></div>

            {/* Buy/Sell Ratio */}
            <div className="w-[116px] shrink-0 flex flex-col items-start justify-center gap-[4px]">
                <div className="bg-[#eee] flex gap-[2px] h-[4px] w-full rounded-[4px] overflow-hidden">
                    <div
                        className="bg-[#2f80ed] h-full"
                        style={{ width: `${(buyRatio / (buyRatio + sellRatio)) * 100}%` }}
                    />
                    <div
                        className="bg-[#e84c3d] h-full"
                        style={{ width: `${(sellRatio / (buyRatio + sellRatio)) * 100}%` }}
                    />
                </div>
                <div className="flex justify-between w-full">
                    <span className="text-[#2f80ed] font-medium text-[10px]">{buyRatio}</span>
                    <span className="text-[#e84c3d] font-medium text-[10px]">{sellRatio}</span>
                </div>
            </div>
        </Link>
    );
};

export default memo(StockRow, (prev, next) => {
    // 가격, 등락률, 순위, 거래량, 매수/매도 비율이 모두 동일하면 리렌더링 방지
    return (
        prev.price === next.price &&
        prev.changeRate === next.changeRate &&
        prev.rank === next.rank &&
        prev.volume === next.volume &&
        prev.buyRatio === next.buyRatio &&
        prev.sellRatio === next.sellRatio
    );
});
