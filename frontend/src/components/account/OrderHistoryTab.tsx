import { useEffect, useMemo, useState } from "react";
import { useAccountStore, type Order } from "../../store/useAccountStore";
import { HistoryDetailModal } from "./HistoryDetailModal";
import { OrderDetail } from "./OrderDetail";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useNotificationStore } from "../../store/useNotificationStore";

export function OrderHistoryTab() {
    const { pendingOrders, completedOrders, fetchPendingOrders, fetchCompletedOrders, cancelOrder, ordersPage, ordersTotalPages, pendingOrdersPage, pendingOrdersTotalPages } = useAccountStore();
    const [selectedMonth, setSelectedMonth] = useState<string>('전체');
    const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
    const [currentPage, setCurrentPage] = useState<number>(0);
    const [currentPendingPage, setCurrentPendingPage] = useState<number>(0);

    useEffect(() => {
        fetchPendingOrders({ page: currentPendingPage, size: 10 });
    }, [fetchPendingOrders, currentPendingPage]);

    useEffect(() => {
        fetchCompletedOrders({ page: currentPage, size: 20 });
    }, [fetchCompletedOrders, currentPage]);

    const availableMonths = useMemo(() => {
        const months = new Set<string>();
        completedOrders.forEach(o => {
            const m = o.date.split('.')[0];
            months.add(m);
        });
        const sorted = Array.from(months).sort((a, b) => parseInt(b) - parseInt(a));
        return ['전체', ...sorted];
    }, [completedOrders]);

    const filteredCompleted = useMemo(() => {
        if (selectedMonth === '전체') return completedOrders;
        return completedOrders.filter(o => o.date.split('.')[0] === selectedMonth);
    }, [completedOrders, selectedMonth]);

    const historyOrders = filteredCompleted;

    // 일자별 그룹화 로직 (완료/취소된 주문만)
    const groupedOrders = historyOrders.reduce((acc: Record<string, Order[]>, order) => {
        if (!acc[order.date]) {
            acc[order.date] = [];
        }
        acc[order.date].push(order);
        return acc;
    }, {});

    const orderDates = Object.keys(groupedOrders).sort((a, b) => {
        const [monthA, dayA] = a.split('.').map(Number);
        const [monthB, dayB] = b.split('.').map(Number);

        if (monthA !== monthB) {
            return monthB - monthA;
        }
        return dayB - dayA;
    });

    return (
        <div className="flex-[1] min-w-0 relative flex flex-col p-6 w-full h-full overflow-y-auto bg-[#f9fafb]">
            <div className="flex flex-col gap-6 pb-12 w-full mt-2">

                {/* --- 대기중인 주문 Section --- */}
                {pendingOrders.length > 0 && (
                    <div className="flex flex-col gap-4 w-full">
                        <div className="flex justify-between items-center w-full">
                            <h2 className="font-bold text-lg text-[#101828]">대기중인 주문</h2>
                        </div>

                        <div className="flex flex-col gap-3">
                            {pendingOrders.map(order => (
                                <div
                                    key={order.id}
                                    onClick={() => setSelectedOrder(order)}
                                    className="bg-white rounded-2xl p-4 shadow-[0_1px_2px_rgba(0,0,0,0.02)] border-[#f3f4f6] border-[0.5px] border-solid flex justify-between items-center gap-4 cursor-pointer hover:bg-slate-50 transition-colors"
                                >
                                    <div className="flex items-stretch gap-3">
                                        <div className="bg-[#e4fff1] text-[#00b25e] px-3 rounded-lg text-sm font-bold flex items-center justify-center shrink-0">
                                            대기
                                        </div>
                                        <div className="flex flex-col justify-center py-1">
                                            <div className="flex items-center gap-1.5">
                                                <h3 className="font-bold text-[#101828] text-base">{order.stockName}</h3>
                                                <span className="font-bold text-[#101828] text-base">{order.type === 'buy' ? '구매' : '판매'}</span>
                                            </div>
                                            <div className="flex items-center gap-2 mt-0.5">
                                                <p className="text-[#6a7282] text-sm font-medium">
                                                    {order.quantity}주 · {Math.round(order.price / order.quantity).toLocaleString()}원
                                                </p>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2 shrink-0">
                                        {order.status === 'canceling' ? (
                                            <span className="text-[#99a1af] font-bold text-sm px-4 py-2.5">
                                                취소중
                                            </span>
                                        ) : (
                                            <>
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); /* TODO: 수정 기능 */ }}
                                                    className="bg-[#f9fafb] text-[#4a5565] font-bold text-sm px-4 py-2.5 rounded-lg hover:bg-slate-100 transition-colors"
                                                >
                                                    수정
                                                </button>
                                                <button
                                                    onClick={async (e) => {
                                                        e.stopPropagation();
                                                        if (window.confirm("정말 주문을 취소하시겠습니까?")) {
                                                            try {
                                                                 await cancelOrder(order.id);
                                                            } catch (error: any) {
                                                                alert(error.message || "주문 취소에 실패했습니다.");
                                                            }
                                                        }
                                                    }}
                                                    className="bg-[#f9fafb] text-[#4a5565] font-bold text-sm px-4 py-2.5 rounded-lg hover:bg-slate-100 transition-colors"
                                                >
                                                    취소
                                                </button>
                                            </>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Pending Pagination */}
                        {pendingOrdersTotalPages > 1 && (
                            <div className="flex justify-center items-center gap-2 mt-4 mb-4">
                                <button
                                    disabled={pendingOrdersPage === 0}
                                    onClick={() => setCurrentPendingPage(prev => Math.max(0, prev - 1))}
                                    className={`p-1.5 rounded-lg ${pendingOrdersPage === 0 ? 'text-[#d1d5db] cursor-not-allowed' : 'text-[#6a7282] hover:bg-slate-100'}`}
                                >
                                    <ChevronLeft className="w-4 h-4" />
                                </button>

                                {Array.from({ length: pendingOrdersTotalPages })
                                    .map((_, i) => i)
                                    .filter(i => {
                                        const start = Math.max(0, Math.min(pendingOrdersPage - 2, pendingOrdersTotalPages - 5));
                                        const end = Math.min(pendingOrdersTotalPages - 1, start + 4);
                                        return i >= start && i <= end;
                                    })
                                    .map(i => (
                                        <button
                                            key={i}
                                            onClick={() => setCurrentPendingPage(i)}
                                            className={`w-7 h-7 flex items-center justify-center rounded-lg font-bold text-sm transition-colors ${
                                                pendingOrdersPage === i
                                                    ? 'bg-[#101828] text-white'
                                                    : 'text-[#6a7282] hover:bg-slate-100'
                                            }`}
                                        >
                                            {i + 1}
                                        </button>
                                    ))}

                                <button
                                    disabled={pendingOrdersPage >= pendingOrdersTotalPages - 1}
                                    onClick={() => setCurrentPendingPage(prev => Math.min(pendingOrdersTotalPages - 1, prev + 1))}
                                    className={`p-1.5 rounded-lg ${pendingOrdersPage >= pendingOrdersTotalPages - 1 ? 'text-[#d1d5db] cursor-not-allowed' : 'text-[#6a7282] hover:bg-slate-100'}`}
                                >
                                    <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        )}
                    </div>
                )}

                {/* --- 완료된 주문 Section --- */}
                <div className="flex flex-col gap-4 w-full mt-4">
                    <div className="flex justify-between items-center w-full">
                        <h2 className="font-bold text-lg text-[#101828]">완료된 주문</h2>
                        <Select value={selectedMonth} onValueChange={setSelectedMonth}>
                            <SelectTrigger className="w-fit border-none bg-transparent font-bold text-[#101828] shadow-none p-0 h-auto focus:ring-0 [&>svg]:text-[#99a1af] gap-1 text-sm text-right">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent align="end" className="rounded-xl shadow-lg border-[#f3f4f6]">
                                {availableMonths.map(m => (
                                    <SelectItem key={m} value={m} className="font-medium cursor-pointer rounded-lg m-1">
                                        {m === '전체' ? '전체' : `2026년 ${m}월`}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="flex flex-col gap-6">
                        {orderDates.map(date => (
                            <div key={date} className="flex flex-col gap-3 w-full">
                                {/* Date Header */}
                                <h3 className="font-bold text-[#101828] text-sm px-1">
                                    {date}
                                </h3>

                                {/* Items List */}
                                <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col rounded-xl shadow-[0_1px_2px_rgba(0,0,0,0.02)] overflow-hidden w-full">
                                    {groupedOrders[date].map((order, index) => {
                                        const isCanceled = order.status === 'canceled';
                                        const isCompleted = order.status === 'completed';

                                        return (
                                            <div
                                                key={order.id}
                                                onClick={() => setSelectedOrder(order)}
                                                className={`flex items-start justify-between p-4 w-full cursor-pointer hover:bg-slate-50 transition-colors ${index < groupedOrders[date].length - 1 ? 'border-b border-[#f3f4f6]' : ''
                                                    }`}
                                            >
                                                <div className="flex flex-col gap-1">
                                                    <p className={`font-bold text-[15px] ${isCanceled ? 'text-[#99a1af]' : 'text-[#101828]'}`}>
                                                        {order.stockName}
                                                    </p>
                                                    <div className="flex items-center gap-2 text-sm text-[#6a7282]">
                                                        {/* 주문 상태 */}
                                                        {isCompleted ? (
                                                            <span className={order.type.toLowerCase() === 'buy' ? "text-[#fb2c36]" : "text-blue-500"}>
                                                                {order.type.toLowerCase() === 'buy' ? '구매완료' : '판매완료'}
                                                            </span>
                                                        ) : isCanceled ? (
                                                            <span className="text-[#99a1af]">
                                                                {order.type.toLowerCase() === 'buy' ? '구매취소' : '판매취소'}
                                                            </span>
                                                        ) : order.status === 'canceling' ? (
                                                            <span className="text-[#99a1af]">
                                                                {order.type.toLowerCase() === 'buy' ? '구매취소중' : '판매취소중'}
                                                            </span>
                                                        ) : (
                                                            <span className="text-blue-500">진행중</span>
                                                        )}

                                                        <span className="text-[#d1d5db]">|</span>

                                                        {/* 수량 */}
                                                        <span className={isCanceled ? 'text-[#99a1af]' : 'text-[#6a7282]'}>
                                                            {order.quantity}주
                                                        </span>
                                                    </div>
                                                </div>

                                                <div className="flex flex-col items-end gap-1">
                                                    <p className={`font-bold text-base text-right ${isCanceled ? 'hidden' : 'text-[#101828]'}`}>
                                                        {order.price.toLocaleString()}원
                                                    </p>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Pagination */}
                    {ordersTotalPages > 1 && (
                        <div className="flex justify-center items-center gap-2 mt-6">
                            <button
                                disabled={ordersPage === 0}
                                onClick={() => setCurrentPage(prev => Math.max(0, prev - 1))}
                                className={`p-2 rounded-lg ${ordersPage === 0 ? 'text-[#d1d5db] cursor-not-allowed' : 'text-[#6a7282] hover:bg-slate-100'}`}
                            >
                                <ChevronLeft className="w-5 h-5" />
                            </button>

                            {Array.from({ length: ordersTotalPages })
                                .map((_, i) => i)
                                .filter(i => {
                                    const start = Math.max(0, Math.min(ordersPage - 2, ordersTotalPages - 5));
                                    const end = Math.min(ordersTotalPages - 1, start + 4);
                                    return i >= start && i <= end;
                                })
                                .map(i => (
                                    <button
                                        key={i}
                                        onClick={() => setCurrentPage(i)}
                                        className={`w-8 h-8 flex items-center justify-center rounded-lg font-bold text-sm transition-colors ${
                                            ordersPage === i
                                                ? 'bg-[#101828] text-white'
                                                : 'text-[#6a7282] hover:bg-slate-100'
                                        }`}
                                    >
                                        {i + 1}
                                    </button>
                                ))}

                            <button
                                disabled={ordersPage >= ordersTotalPages - 1}
                                onClick={() => setCurrentPage(prev => Math.min(ordersTotalPages - 1, prev + 1))}
                                className={`p-2 rounded-lg ${ordersPage >= ordersTotalPages - 1 ? 'text-[#d1d5db] cursor-not-allowed' : 'text-[#6a7282] hover:bg-slate-100'}`}
                            >
                                <ChevronRight className="w-5 h-5" />
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Detail Modal Layer */}
            <HistoryDetailModal isOpen={!!selectedOrder} onClose={() => setSelectedOrder(null)}>
                {selectedOrder && (
                    <OrderDetail
                        order={selectedOrder}
                        onClose={() => setSelectedOrder(null)}
                    />
                )}
            </HistoryDetailModal>

        </div>
    );
}
