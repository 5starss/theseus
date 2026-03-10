import type { Order } from "../../store/useAccountStore";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface OrderDetailProps {
    order: Order;
    onClose: () => void;
}

export function OrderDetail({ order, onClose }: OrderDetailProps) {
    const isCanceled = order.status === 'canceled';
    const isCompleted = order.status === 'completed';

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('ko-KR').format(Math.round(value)) + '원';
    };

    // Mock an order timestamp safely using the mock data date (e.g., "2.22" -> "2024년 2월 22일 09:57")
    const [month, day] = order.date.split('.');
    const timestampStr = `2024년 ${month}월 ${day}일 09:57`;

    // Price per share (calculating it backward from total price)
    const pricePerShare = Math.round(order.price / order.quantity);

    const typeText = order.type === 'buy' ? '구매' : '판매';

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
                    {formatCurrency(order.price)}
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
                    <span className="text-sm font-medium text-[#101828]">{order.quantity}주</span>
                </div>
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">총 {typeText} 금액</span>
                    <span className="text-sm font-medium text-[#101828]">{formatCurrency(order.price)}</span>
                </div>
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">주문 시각</span>
                    <span className="text-sm font-medium text-[#101828]">{timestampStr}</span>
                </div>
                {(isCompleted || isCanceled) && (
                    <div className="flex justify-between items-center w-full">
                        <span className="text-sm text-[#6a7282]">
                            {isCompleted ? `${typeText} 완료` : `${typeText} 취소`}
                        </span>
                        <span className={`text-sm font-medium ${isCanceled ? 'text-[#99a1af]' : 'text-[#101828]'}`}>
                            {timestampStr}
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
