import { useStockStore } from "../../../store/useStockStore";
import { useAccountStore } from "../../../store/useAccountStore";
import { useAuthStore } from "../../../store/useAuthStore";
import { LoginGuardOverlay } from "../LoginGuardOverlay";

export function MyStockInfo() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const stockName = useStockStore(state => state.stockName);
    const currentPrice = useStockStore(state => state.currentPrice);
    const stockCode = useStockStore(state => state.stockCode);
    const portfolio = useAccountStore(state => state.portfolio);

    // 실제 보유 데이터 찾기
    const myHolding = portfolio.find(p => p.code === stockCode);
    const ownedShares = myHolding ? myHolding.shares : 0;
    const avgPrice = myHolding ? myHolding.avgPrice : 0;

    // 계산식 적용
    const totalValue = currentPrice * ownedShares;
    const totalProfit = ownedShares > 0 ? totalValue - (avgPrice * ownedShares) : 0;
    const profitRate = (ownedShares > 0 && avgPrice > 0) ? (totalProfit / (avgPrice * ownedShares)) * 100 : 0;
    const isProfit = totalProfit >= 0;

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 h-full flex flex-col relative overflow-hidden">
            {/* 로그인 필요 시 오버레이 */}
            {!isLoggedIn && <LoginGuardOverlay />}

            <div className={`flex flex-col h-full ${!isLoggedIn ? 'opacity-30 pointer-events-none blur-[2px]' : ''}`}>
                <div className="flex justify-between items-end mb-4 pr-1">
                    <h3 className="font-bold text-slate-800">내 주식</h3>
                    <span className="text-xs font-medium text-slate-500">{stockName}</span>
                </div>

                <div className="flex flex-col gap-2.5">
                    <div className="flex justify-between items-center bg-slate-50 px-3 py-2 rounded-md">
                        <span className="text-xs font-semibold text-slate-500">보유수량</span>
                        <span className="text-sm font-bold text-slate-800">{ownedShares.toLocaleString()}주</span>
                    </div>
                    <div className="flex justify-between items-center bg-slate-50 px-3 py-2 rounded-md">
                        <span className="text-xs font-semibold text-slate-500">평가금액</span>
                        <span className="text-sm font-bold text-slate-800">{totalValue.toLocaleString()}</span>
                    </div>

                    <div className="h-px w-full bg-slate-100 my-1"></div>

                    <div className="flex justify-between items-center">
                        <span className="text-[11px] font-medium text-slate-500 pl-1">평가손익</span>
                        <span className={`text-xs font-bold pr-1 ${isProfit ? 'text-red-500' : 'text-blue-500'}`}>
                            {isProfit ? '+' : ''}{totalProfit.toLocaleString()}
                        </span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-[11px] font-medium text-slate-500 pl-1">수익률</span>
                        <span className={`text-xs font-bold pr-1 ${isProfit ? 'text-red-500' : 'text-blue-500'}`}>
                            {isProfit ? '+' : ''}{profitRate.toFixed(2)}%
                        </span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-[11px] font-medium text-slate-500 pl-1">1주 평균 금액</span>
                        <span className="text-xs font-semibold text-slate-700 pr-1">{avgPrice.toLocaleString()}</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
