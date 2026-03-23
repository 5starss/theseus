import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAccountStore } from "../../../store/useAccountStore";
import { useAuthStore } from "../../../store/useAuthStore";
import { ScrollArea } from "../../ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { AccountType } from "../../../api/account";

export function HoldingsSection() {
    const navigate = useNavigate();
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const {
        cashBalance,
        totalInvested,
        totalEvaluated,
        portfolio,
        currentAccountType,
        setAccountType
    } = useAccountStore();

    const totalProfit = totalEvaluated - totalInvested;
    const profitRate = totalInvested > 0 ? (totalProfit / totalInvested) * 100 : 0;
    const profitColor = totalProfit > 0 ? 'text-red-500' : totalProfit < 0 ? 'text-blue-500' : 'text-slate-500';

    return (
        <div className="flex flex-col h-full w-[320px] min-w-[320px]">
            <div className="p-6 border-b border-slate-100">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-bold text-slate-800">내 주식</h2>
                    {isLoggedIn && (
                        <Select
                            value={currentAccountType}
                            onValueChange={(val) => setAccountType(val as AccountType)}
                        >
                            <SelectTrigger className="w-fit h-8 border-none bg-slate-100/50 hover:bg-slate-100 rounded-lg font-bold text-xs text-slate-600 gap-1 px-2.5 transition-all focus:ring-0 shadow-none">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent
                                align="end"
                                position="popper"
                                sideOffset={4}
                                className="rounded-xl border-slate-100 shadow-xl overflow-hidden min-w-[140px] z-50"
                            >
                                <SelectItem value="USER" className="text-xs font-bold py-2.5 cursor-pointer rounded-lg my-1">기본계좌</SelectItem>
                                <SelectItem value="AI" className="text-xs font-bold py-2.5 cursor-pointer rounded-lg my-1">AI계좌</SelectItem>
                            </SelectContent>
                        </Select>
                    )}
                </div>

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
                            <p className="text-xs text-slate-400 font-medium mb-1">총 평가 자산</p>
                            <div className="flex items-baseline gap-2">
                                <p className="text-lg font-bold text-slate-800">{totalEvaluated.toLocaleString()}원</p>
                                <div className={`flex items-center text-xs font-bold ${profitColor}`}>
                                    {totalProfit > 0 ? <TrendingUp className="w-3 h-3 mr-0.5" /> : totalProfit < 0 ? <TrendingDown className="w-3 h-3 mr-0.5" /> : <Minus className="w-3 h-3 mr-0.5" />}
                                    {Math.abs(totalProfit).toLocaleString()}원 ({profitRate >= 0 ? '+' : ''}{profitRate.toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <ScrollArea className="flex-1">
                <div className="py-2">
                    <div className="px-6 mb-2">
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">보유 주식 {portfolio.length}</span>
                    </div>

                    <div className="flex flex-col">
                        {portfolio.length === 0 ? (
                            <p className="text-center py-10 text-slate-400 text-sm">보유하신 주식이 없습니다.</p>
                        ) : (
                            portfolio.map((item) => {
                                const profit = (item.currentPrice - item.avgPrice) * item.shares;
                                const rate = item.avgPrice > 0 ? ((item.currentPrice - item.avgPrice) / item.avgPrice) * 100 : 0;
                                const color = profit > 0 ? 'text-red-500' : profit < 0 ? 'text-blue-500' : 'text-slate-500';

                                return (
                                    <div
                                        key={item.code}
                                        onClick={() => navigate(`/stock/${item.code}`)}
                                        className="px-6 py-3 hover:bg-slate-50 transition-all cursor-pointer group border-b border-transparent hover:border-slate-100"
                                    >
                                        <div className="flex justify-between items-center">
                                            {/* 왼쪽: 종목명 및 수량 */}
                                            <div className="flex flex-col gap-0.5">
                                                <h3 className="font-bold text-sm text-slate-800 group-hover:text-blue-600 transition-colors">{item.name}</h3>
                                                <p className="text-[10px] text-slate-400 font-medium">{item.shares.toLocaleString()}주</p>
                                            </div>

                                            {/* 오른쪽: 총금액 및 수익(수익률) */}
                                            <div className="flex flex-col items-end gap-0.5">
                                                <p className="text-sm font-bold text-slate-800">{(item.currentPrice * item.shares).toLocaleString()}원</p>
                                                <div className={`flex items-center text-[10px] font-bold ${color}`}>
                                                    <span>{profit >= 0 ? '+' : ''}{profit.toLocaleString()}원</span>
                                                    <span className="ml-1">({profit >= 0 ? '+' : ''}{rate.toFixed(2)}%)</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })
                        )}
                    </div>
                </div>
            </ScrollArea>
        </div>
    );
}
