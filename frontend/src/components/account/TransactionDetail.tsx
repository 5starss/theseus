import type { Transaction } from "../../store/useAccountStore";
import { Button } from "@/components/ui/button";

interface TransactionDetailProps {
    transaction: Transaction;
    onClose: () => void;
}

export function TransactionDetail({ transaction, onClose }: TransactionDetailProps) {
    const isIncome = transaction.amount > 0;
    const typeLabel = transaction.type === 'buy' ? '구매' : transaction.type === 'sell' ? '판매' : transaction.type === 'deposit' ? '입금' : '출금';

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('ko-KR').format(Math.round(value)) + '원';
    };

    return (
        <div className="flex flex-col p-6 w-full">
            {/* Header */}
            <div className="flex flex-col gap-1 mb-6">
                <h3 className="font-bold text-[#101828] text-lg">{transaction.stockName || transaction.description}</h3>
                <p className="text-sm text-[#6a7282]">{transaction.date} {transaction.time}</p>
            </div>

            {/* Highlight Box */}
            <div className="bg-[#f9fafb] rounded-xl p-4 flex flex-col gap-1 mb-6">
                <p className="text-xs text-[#6a7282]">{typeLabel}</p>
                <p className={`font-bold text-2xl ${isIncome ? 'text-[#fb2c36]' : 'text-[#101828]'}`}>
                    {isIncome ? '+' : ''}{formatCurrency(transaction.amount)}
                </p>
            </div>

            {/* Detailed Info List */}
            <div className="flex flex-col gap-4 mb-8">
                <h4 className="font-bold text-[#101828] text-sm mb-1">상세 정보</h4>
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">거래유형</span>
                    <span className="text-sm font-medium text-[#101828]">{typeLabel}</span>
                </div>
                {transaction.stockName && (
                    <div className="flex justify-between items-center w-full">
                        <span className="text-sm text-[#6a7282]">종목명</span>
                        <span className="text-sm font-medium text-[#101828]">{transaction.stockName}</span>
                    </div>
                )}
                {transaction.quantity && (
                    <div className="flex justify-between items-center w-full">
                        <span className="text-sm text-[#6a7282]">수량</span>
                        <span className="text-sm font-medium text-[#101828]">{transaction.quantity}주</span>
                    </div>
                )}
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">거래금액</span>
                    <span className="text-sm font-medium text-[#101828]">{formatCurrency(Math.abs(transaction.amount))}</span>
                </div>
                <div className="flex justify-between items-center w-full">
                    <span className="text-sm text-[#6a7282]">거래 후 잔액</span>
                    <span className="text-sm font-medium text-[#101828]">{formatCurrency(transaction.remainingBalance)}</span>
                </div>
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
