import { memo } from "react";

import { useStockStore } from "../../store/useStockStore";
import { useAuthStore } from "../../store/useAuthStore";
import { LoginGuardOverlay } from "./LoginGuardOverlay";

export const Orderbook = memo(function Orderbook() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const askPrice = useStockStore(state => state.askPrice);
    const askVolume = useStockStore(state => state.askVolume);
    const bidPrice = useStockStore(state => state.bidPrice);
    const bidVolume = useStockStore(state => state.bidVolume);

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 h-full flex flex-col">
            <h3 className="font-bold text-slate-800 mb-3 ml-1">호가</h3>

            <div className="flex-1 flex flex-col bg-slate-50 border border-slate-100 rounded-lg overflow-hidden relative">
                {/* 로그인 필요 시 오버레이 */}
                {!isLoggedIn && <LoginGuardOverlay />}

                <div className={`flex-1 flex flex-col h-full ${!isLoggedIn ? 'opacity-30 pointer-events-none blur-[2px]' : ''}`}>
                    <div className="flex-1 flex flex-col justify-end border-b border-slate-200">
                        <div className="flex h-12 w-full hover:bg-slate-100 transition-colors cursor-pointer group relative">
                            <div className="w-1/3"></div>
                            <div className="w-1/3 flex items-center justify-center font-bold text-blue-600 bg-blue-50/30 border-l border-r border-slate-100">
                                {askPrice.toLocaleString()}
                            </div>
                            <div className="w-1/3 flex items-center justify-between px-3 text-sm font-medium text-slate-600">
                                <span>{askVolume.toLocaleString()}</span>
                                <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">잔량</span>
                            </div>
                            <div className="absolute right-0 top-0 h-full bg-blue-100/50" style={{ width: `${Math.min(askVolume / 200, 100)}%` }} />
                        </div>
                    </div>

                    <div className="flex-1 flex flex-col justify-start">
                        <div className="flex h-12 w-full hover:bg-slate-100 transition-colors cursor-pointer group relative">
                            <div className="w-1/3 flex items-center justify-between px-3 text-sm font-medium text-slate-600">
                                <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">잔량</span>
                                <span>{bidVolume.toLocaleString()}</span>
                            </div>
                            <div className="w-1/3 flex items-center justify-center font-bold text-red-600 bg-red-50/30 border-l border-r border-slate-100 relative z-10">
                                {bidPrice.toLocaleString()}
                            </div>
                            <div className="w-1/3"></div>
                            <div className="absolute left-0 top-0 h-full bg-red-100/50" style={{ width: `${Math.min(bidVolume / 200, 100)}%` }} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
});
