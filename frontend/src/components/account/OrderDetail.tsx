import { useEffect, useState } from "react";
import type { Order } from "../../store/useAccountStore";
import { X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { orderApi, type OrderDetailResponse, type OrderHistoryDetailResponse } from "../../api/order";

interface OrderDetailProps {
    order: Order;
    onClose: () => void;
}

export function OrderDetail({ order, onClose }: OrderDetailProps) {
    const [loading, setLoading] = useState(true);
    const [detail, setDetail] = useState<OrderDetailResponse | OrderHistoryDetailResponse | null>(null);

    const isPending = order.status === 'pending';
    const isCanceled = order.status === 'canceled';
    const isCompleted = order.status === 'completed';

    useEffect(() => {
        const fetchDetail = async () => {
            setLoading(true);
            try {
                if (isPending) {
                    const data = await orderApi.getOrderDetail(order.id);
                    setDetail(data);
                } else {
                    const data = await orderApi.getHistoryDetail(order.id);
                    setDetail(data);
                }
            } catch (error) {
                console.error("Failed to fetch order detail:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchDetail();
    }, [order.id, isPending]);

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('ko-KR').format(Math.round(value)) + '원';
    };

    const formatDate = (isoDate?: string) => {
        if (!isoDate) return "-";
        const date = new Date(isoDate);
        return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
    };

    // Use fetched data or fallback to props
    const displayPrice = detail ? (isPending ? (detail as OrderDetailResponse).orderAmount : (detail as OrderHistoryDetailResponse).totalAmount) : order.price;
    const displayQuantity = detail ? (isPending ? (detail as OrderDetailResponse).orderQuantity : (detail as OrderHistoryDetailResponse).quantity) : order.quantity;
    const pricePerShare = detail ? detail.pricePerShare : Math.round(order.price / order.quantity);
    const orderTime = detail ? formatDate(detail.orderCreatedAt) : "-";
    const statusTime = detail && !isPending ? formatDate((detail as OrderHistoryDetailResponse).createdAt) : "-";

    const typeText = order.type === 'buy' ? '구매' : '판매';

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center p-12 w-full min-h-[400px]">
                <Loader2 className="animate-spin text-[#155dfc] mb-2" size={32} />
                <p className="text-[#6a7282] text-sm">주문 정보를 불러오고 있습니다...</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col p-6 w-full relative">
            {/* Header */}
            <div className="flex justify-between items-start mb-6 pr-8">
                <div className="flex flex-col gap-1">
                    <h3 className="font-bold text-[#101828] text-lg">{order.stockName}</h3>
                </div>
                <button onClick={onClose} className="absolute top-6 right-6 text-[#99a1af] hover:text-[#4a5565] transition-colors">
                    <X size={20} />
                </button>
            </div>

            {/* Highlight Box */}
            <div className="bg-[#f9fafb] rounded-xl p-4 flex flex-col gap-1 mb-6">
                <p className="text-xs text-[#6a7282]">총 {typeText} 금액</p>
                <p className={`font-bold text-2xl ${isCanceled ? 'text-[#99a1af] line-through' : 'text-[#101828]'}`}>
                    {formatCurrency(displayPrice)}
                </p>
            </div>

            {/* Detailed Info List */}
            <div className="flex flex-col gap-4 mb-8">
                <h4 className="font-bold text-[#101828] text-sm mb-1">상세 정보</h4>
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">1주 {typeText} 가격</span>
                    <span className="text-sm font-medium text-[#101828]">{formatCurrency(pricePerShare)}</span>
                </div>
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">{typeText} 수량</span>
                    <span className="text-sm font-medium text-[#101828]">{displayQuantity}주</span>
                </div>
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">총 {typeText} 금액</span>
                    <span className="text-sm font-medium text-[#101828]">{formatCurrency(displayPrice)}</span>
                </div>
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">주문 시각</span>
                    <span className="text-sm font-medium text-[#101828]">{orderTime}</span>
                </div>
                {(isCompleted || isCanceled) && (
                    <div className="flex justify-between items-center w-full">
                        <span className="text-sm text-[#6a7282]">
                            {isCompleted ? `${typeText} 완료` : `${typeText} 취소`}
                        </span>
                        <span className={`text-sm font-medium ${isCanceled ? 'text-[#99a1af]' : 'text-[#101828]'}`}>
                            {statusTime}
                        </span>
                    </div>
                )}
            </div>

            {/* Actions */}
            <Button
                onClick={onClose}
                className="w-full h-12 bg-[#155dfc] text-white font-bold rounded-xl hover:bg-[#0e48c4]"
            >
                확인
            </Button>
        </div>
    );
}
