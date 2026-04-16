import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface ConfirmOrderModalProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    stockName: string;
    isBuy: boolean;
    orderPrice: number;
    quantity: number;
    totalAmount: number;
    fee: number;
    tax: number;
    feeRate: number;
    taxRate: number;
    totalWithFeeAndTax: number;
    onConfirm: () => void;
}

export function ConfirmOrderModal({
    isOpen,
    onOpenChange,
    stockName,
    isBuy,
    orderPrice,
    quantity,
    totalAmount,
    fee,
    tax,
    feeRate,
    taxRate,
    totalWithFeeAndTax,
    onConfirm
}: ConfirmOrderModalProps) {
    return (
        <Dialog open={isOpen} onOpenChange={onOpenChange}>
            <DialogContent className="w-[320px] rounded-2xl p-6 bg-white gap-0 border-none">
                <DialogTitle className="text-center text-lg font-bold mb-6 text-slate-800">
                    {stockName} {isBuy ? '매수' : '매도'} 알림
                </DialogTitle>
                <DialogDescription className="sr-only">주문 내용을 확인합니다.</DialogDescription>

                <div className="flex flex-col gap-4 mb-6">
                    <div className="flex justify-between items-center bg-slate-50 p-3 rounded-lg">
                        <span className="text-xs font-semibold text-slate-500">주문 단가</span>
                        <span className="text-sm font-bold text-slate-800">{orderPrice.toLocaleString()}원</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-xs font-medium text-slate-500 pl-1">주문 수량</span>
                        <span className="text-sm font-bold text-slate-800 pr-1">{quantity}주</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-xs font-medium text-slate-500 pl-1">주문 금액</span>
                        <span className="text-sm font-bold text-slate-800 pr-1">{totalAmount.toLocaleString()}원</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-xs font-medium text-slate-500 pl-1">
                            수수료 <span className="text-[10px] text-slate-400">({(feeRate * 100).toFixed(3)}%)</span>
                        </span>
                        <span className="text-sm font-bold text-slate-800 pr-1">{fee.toLocaleString()}원</span>
                    </div>
                    {!isBuy && (
                        <div className="flex justify-between items-center">
                            <span className="text-xs font-medium text-slate-500 pl-1">
                                증권거래세 <span className="text-[10px] text-slate-400">({(taxRate * 100).toFixed(2)}%)</span>
                            </span>
                            <span className="text-sm font-bold text-slate-800 pr-1">{tax.toLocaleString()}원</span>
                        </div>
                    )}
                    <div className="h-px bg-slate-100 my-1 w-full relative">
                        <div className="absolute top-1/2 -translate-y-1/2 left-1/2 -translate-x-1/2 bg-[#f8fafc] w-6 h-6 flex items-center justify-center rounded-full border border-slate-100">
                            <span className="text-[16px] text-[#fb2c36] font-bold pb-1">=</span>
                        </div>
                    </div>
                    <div className="flex flex-col items-center mt-2 bg-[#f8fafc] p-4 rounded-xl border border-slate-100">
                        <span className="text-[11px] font-semibold text-slate-500 mb-1">
                            {isBuy ? '실제 출금 금액' : '실제 입금 금액'}
                        </span>
                        <span className={`text-xl font-bold ${isBuy ? 'text-[#ce242b]' : 'text-[#0e48c4]'}`}>
                            {totalWithFeeAndTax.toLocaleString()}원
                        </span>
                    </div>
                </div>

                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        className="flex-1 py-6 bg-slate-100 border-none text-slate-500 font-bold hover:bg-slate-200 hover:text-slate-600 rounded-xl"
                        onClick={() => onOpenChange(false)}
                    >
                        취소
                    </Button>
                    <Button
                        className={`flex-1 py-6 text-white font-bold rounded-xl
                            ${isBuy ? 'bg-[#fb2c36] hover:bg-[#e02730]' : 'bg-[#155dfc] hover:bg-[#124bc9]'}`}
                        onClick={onConfirm}
                    >
                        {isBuy ? "구매" : "판매"}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
