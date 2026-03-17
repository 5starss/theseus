import { useStockStore } from "../../store/useStockStore";

export function StockHeader() {
    const { stockCode, stockName, currentPrice, priceChange, changeRate } = useStockStore();
    const isPositive = priceChange > 0;
    const isNegative = priceChange < 0;
    const colorClass = isPositive ? 'text-red-500' : isNegative ? 'text-blue-500' : 'text-slate-800';
    const sign = isPositive ? '▲' : isNegative ? '▼' : '-';
    const plusSign = isPositive ? '+' : '';

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex items-center gap-8">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold shrink-0">
                    {stockName ? stockName.charAt(0) : 'S'}
                </div>
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
        </div>
    );
}

