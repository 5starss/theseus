import { memo } from "react";

import { useStockStore } from "../../store/useStockStore";
import { useAuthStore } from "../../store/useAuthStore";
import { LoginGuardOverlay } from "./LoginGuardOverlay";

export const Orderbook = memo(function Orderbook() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const currentPrice = useStockStore(state => state.currentPrice);
    const prevClose = useStockStore(state => state.prevClose);
    const askPrice = useStockStore(state => state.askPrice);
    const askVolume = useStockStore(state => state.askVolume);
    const bidPrice = useStockStore(state => state.bidPrice);
    const bidVolume = useStockStore(state => state.bidVolume);
    const setSelectedOrderPrice = useStockStore(state => state.setSelectedOrderPrice);

    const isCurrentAsk = currentPrice === askPrice && currentPrice > 0;
    const isCurrentBid = currentPrice === bidPrice && currentPrice > 0;

    const renderPriceWithRate = (price: number) => {
        if (price === 0) return null;
        const rate = prevClose > 0 ? ((price - prevClose) / prevClose) * 100 : 0;
        const rateText = `${rate > 0 ? '+' : ''}${rate.toFixed(2)}%`;
        const rateColor = rate > 0 ? "text-red-500" : rate < 0 ? "text-blue-500" : "text-slate-400";

        return (
            <div className="flex flex-col items-center">
                <span className={`leading-tight ${rateColor}`}>{price.toLocaleString()}</span>
                <span className={`text-[10px] font-medium leading-tight ${rateColor}`}>{rateText}</span>
            </div>
        );
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 h-full flex flex-col">
            <h3 className="font-bold text-slate-800 mb-3 ml-1">호가</h3>

            <div className="flex-1 flex flex-col bg-slate-50 border border-slate-100 rounded-lg overflow-hidden relative">
                {/* 로그인 필요 시 오버레이 */}
                {!isLoggedIn && <LoginGuardOverlay />}

                <div className={`flex-1 flex flex-col h-full ${!isLoggedIn ? 'opacity-30 pointer-events-none blur-[2px]' : ''}`}>
                    <div className="flex-1 border-b border-slate-200 overflow-hidden">
                        <div 
                            className="flex h-full w-full transition-colors cursor-pointer group relative hover:bg-slate-100/50"
                            onClick={() => setSelectedOrderPrice(askPrice)}
                        >
                            <div className="w-1/3 flex items-center justify-between px-3 text-sm font-medium text-blue-600 relative overflow-hidden">
                                <div className="absolute inset-0 bg-blue-50/50 opacity-0 group-hover:opacity-100 transition-opacity" />
                                <div className="absolute inset-y-0 right-0 top-1/2 -translate-y-1/2 h-4/6 w-full bg-blue-50/10 transition-colors" />
                                <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity relative z-20">잔량</span>
                                <span className="relative z-20">{askVolume.toLocaleString()}</span>
                                <div className="absolute right-0 top-1/2 -translate-y-1/2 h-4/6 bg-blue-100/60 rounded-l-sm z-10" style={{ width: `${Math.min(askVolume / 200, 100)}%` }} />
                            </div>
                            <div className="w-1/3 flex items-center justify-center font-bold border-l border-r border-slate-100 relative">
                                <div className="absolute inset-0 bg-blue-50/50 opacity-0 group-hover:opacity-100 transition-opacity" />
                                <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-4/6 bg-blue-50/30 transition-colors" />
                                {isCurrentAsk && <div className="absolute inset-0 ring-1 ring-black ring-inset z-30 pointer-events-none rounded" />}
                                <div className="relative z-20">{renderPriceWithRate(askPrice)}</div>
                            </div>
                            <div className="w-1/3"></div>
                        </div>
                    </div>

                    <div className="flex-1 overflow-hidden">
                        <div 
                            className="flex h-full w-full transition-colors cursor-pointer group relative hover:bg-slate-100/50"
                            onClick={() => setSelectedOrderPrice(bidPrice)}
                        >
                            <div className="w-1/3"></div>
                            <div className="w-1/3 flex items-center justify-center font-bold border-l border-r border-slate-100 relative">
                                <div className="absolute inset-0 bg-red-50/50 opacity-0 group-hover:opacity-100 transition-opacity" />
                                <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-4/6 bg-red-50/30 transition-colors" />
                                {isCurrentBid && <div className="absolute inset-0 ring-1 ring-black ring-inset z-30 pointer-events-none rounded" />}
                                <div className="relative z-20">{renderPriceWithRate(bidPrice)}</div>
                            </div>
                            <div className="w-1/3 flex items-center justify-between px-3 text-sm font-medium text-red-600 relative overflow-hidden">
                                <div className="absolute inset-0 bg-red-50/50 opacity-0 group-hover:opacity-100 transition-opacity" />
                                <div className="absolute inset-y-0 left-0 top-1/2 -translate-y-1/2 h-4/6 w-full bg-red-50/10 transition-colors" />
                                <span className="relative z-20">{bidVolume.toLocaleString()}</span>
                                <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity relative z-20">잔량</span>
                                <div className="absolute left-0 top-1/2 -translate-y-1/2 h-4/6 bg-red-100/60 rounded-r-sm z-10" style={{ width: `${Math.min(bidVolume / 200, 100)}%` }} />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
});
