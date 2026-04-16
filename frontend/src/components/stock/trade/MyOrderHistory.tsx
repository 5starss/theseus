import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStockStore } from "../../../store/useStockStore";
import { useAccountStore } from "../../../store/useAccountStore";
import { useAuthStore } from "../../../store/useAuthStore";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LoginGuardOverlay } from "../LoginGuardOverlay";

export function MyOrderHistory() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const navigate = useNavigate();
    const [tab, setTab] = useState<"pending" | "completed">("completed");

    const pendingOrders = useAccountStore(state => state.pendingOrders);
    const completedOrders = useAccountStore(state => state.completedOrders);
    const fetchPendingOrders = useAccountStore(state => state.fetchPendingOrders);
    const fetchCompletedOrders = useAccountStore(state => state.fetchCompletedOrders);
    const stockCode = useStockStore(state => state.stockCode);

    // 현재 종목의 주문 내역만 필터링 (스토어 필드명: stockCode)
    const stockOrders = [...pendingOrders, ...completedOrders].filter((o) => o.stockCode === stockCode);

    const currentOrders = tab === "pending"
        ? stockOrders.filter((o) => o.status === 'pending' || o.status === 'canceling')
        : stockOrders.filter((o) => o.status === 'completed' || o.status === 'canceled');

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 h-full flex flex-col relative overflow-hidden">
            {/* 로그인 필요 시 오버레이 */}
            {!isLoggedIn && <LoginGuardOverlay />}

            <div className={`flex flex-col h-full ${!isLoggedIn ? 'opacity-30 pointer-events-none blur-[2px]' : ''}`}>
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-slate-800">나의 주문내역</h3>
                    <Button variant="ghost" onClick={() => navigate('/account/orders')} className="h-6 px-2 text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors">더보기</Button>
                </div>

                <Tabs
                    value={tab}
                    onValueChange={(val) => {
                        setTab(val as "pending" | "completed");
                        if (val === "pending") fetchPendingOrders();
                        else fetchCompletedOrders({ ticker: stockCode });
                    }}
                    className="mb-4"
                >
                    <TabsList className="w-full h-auto flex gap-2 bg-transparent p-0">
                        <TabsTrigger
                            value="pending"
                            className="flex-1 py-1.5 rounded-md text-xs font-bold transition-colors data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=active]:shadow-none bg-slate-100 text-slate-500 hover:bg-slate-200 shadow-none border-none"
                        >
                            대기
                        </TabsTrigger>
                        <TabsTrigger
                            value="completed"
                            className="flex-1 py-1.5 rounded-md text-xs font-bold transition-colors data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=active]:shadow-none bg-slate-100 text-slate-500 hover:bg-slate-200 shadow-none border-none"
                        >
                            완료
                        </TabsTrigger>
                    </TabsList>
                </Tabs>

                <div className="flex-1 overflow-y-auto pr-1">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="border-b border-slate-200">
                                {tab === "completed" && <th className="pb-2 text-xs font-semibold text-slate-500 w-[20%] text-center">일자</th>}
                                <th className={`pb-2 text-xs font-semibold text-slate-500 ${tab === "pending" ? "w-[20%]" : "w-[20%]"} text-center`}>구분</th>
                                <th className={`pb-2 text-xs font-semibold text-slate-500 ${tab === "pending" ? "w-[30%]" : "w-[35%]"} text-center`}>단가</th>
                                <th className={`pb-2 text-xs font-semibold text-slate-500 ${tab === "pending" ? "w-[20%]" : "w-[25%]"} text-center`}>수량</th>
                                {tab === "pending" && <th className="pb-2 text-xs font-semibold text-slate-500 w-[30%] text-center">관리</th>}
                            </tr>
                        </thead>
                        <tbody>
                            {currentOrders.length === 0 ? (
                                <tr><td colSpan={tab === "pending" ? 5 : 4} className="py-4 text-center text-xs text-slate-400">내역이 없습니다.</td></tr>
                            ) : (
                                currentOrders.map((order, idx) => (
                                    <tr key={idx} className="border-b border-slate-50 last:border-none hover:bg-slate-50/50 transition-colors">
                                        {tab === "completed" && (
                                            <td className="py-2.5 text-xs font-medium text-slate-500 text-center">
                                                {order.date}
                                            </td>
                                        )}
                                        <td className={`py-2.5 text-xs font-bold text-center ${order.status === 'canceled' ? 'text-slate-400' : order.type === 'buy' ? 'text-red-500' : 'text-blue-500'}`}>
                                            {order.status === 'canceled'
                                                ? (order.type === 'buy' ? '매수취소' : '매도취소')
                                                : order.type === 'buy' ? '매수' : '매도'}
                                        </td>
                                        <td className="py-2.5 text-xs font-semibold text-slate-700 text-center">{order.price.toLocaleString()}</td>
                                        <td className="py-2.5 text-xs font-medium text-slate-600 text-center">{order.quantity}주</td>
                                        {tab === "pending" && (
                                            <td className="py-2.5">
                                                <div className="flex items-center justify-center gap-1">
                                                    {order.status === 'canceling' ? (
                                                        <span className="text-slate-400 font-medium text-[10px] px-2 py-1">취소중</span>
                                                    ) : (
                                                        <button
                                                            onClick={async (e) => {
                                                                e.stopPropagation();
                                                                if (window.confirm("정말 주문을 취소하시겠습니까?")) {
                                                                    try {
                                                                        await useAccountStore.getState().cancelOrder(order.id);
                                                                    } catch (err) {
                                                                        const error = err as Error;
                                                                        alert(error.message || "주문 취소에 실패했습니다.");
                                                                    }
                                                                }
                                                            }}
                                                            className="bg-slate-100 text-slate-600 font-medium text-[10px] px-2 py-1 rounded hover:bg-slate-200 transition-colors"
                                                        >
                                                            취소
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        )}
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
