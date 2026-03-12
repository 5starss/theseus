import { useAccountStore, type Transaction } from "../../store/useAccountStore";
import { useEffect, useMemo, useState } from "react";
import { HistoryDetailModal } from "./HistoryDetailModal";
import { TransactionDetail } from "./TransactionDetail";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const TransactionHistoryTab = () => {
    const { cashBalance, transactions, fetchTransactions } = useAccountStore();
    const [selectedMonth, setSelectedMonth] = useState<string>('전체');
    const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);

    useEffect(() => {
        fetchTransactions();
    }, [fetchTransactions]);

    const availableMonths = useMemo(() => {
        const months = new Set<string>();
        transactions.forEach(t => {
            const m = t.date.split('.')[0];
            months.add(m);
        });
        const sorted = Array.from(months).sort((a, b) => parseInt(b) - parseInt(a));
        return ['전체', ...sorted];
    }, [transactions]);

    const filteredTransactions = useMemo(() => {
        if (selectedMonth === '전체') return transactions;
        return transactions.filter(t => t.date.split('.')[0] === selectedMonth);
    }, [transactions, selectedMonth]);

    // Group transactions by date
    const groupedTransactions = useMemo(() => {
        const groups: Record<string, typeof filteredTransactions> = {};
        filteredTransactions.forEach(t => {
            if (!groups[t.date]) {
                groups[t.date] = [];
            }
            groups[t.date].push(t);
        });

        // Sort dates descending (simple string compare works for our mock dates like '2.25' vs '2.11')
        return Object.keys(groups)
            .sort((a, b) => parseFloat(b) - parseFloat(a))
            .map(date => ({
                date,
                items: groups[date]
            }));
    }, [filteredTransactions]);

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('ko-KR').format(Math.round(value)) + '원';
    };

    return (
        <div className="flex-[1] min-w-0 relative flex flex-col p-6 w-full h-full overflow-y-auto bg-[#f9fafb]">
            <div className="flex flex-col gap-6 pb-12 w-full">

                {/* Header Card: Available Order Amount */}
                <div className="bg-[#f9fafb] flex flex-col gap-1 pt-4 pr-4 rounded-xl w-full">
                    <p className="text-[#6a7282] text-xs">주문 가능 금액</p>
                    <p className="font-bold text-[#101828] text-2xl">
                        {formatCurrency(cashBalance)}
                    </p>
                </div>

                {/* Filter Dropdown */}
                <div className="mt-4 flex">
                    <Select value={selectedMonth} onValueChange={setSelectedMonth}>
                        <SelectTrigger className="w-fit border-none bg-transparent font-bold text-[#101828] shadow-none p-0 h-auto focus:ring-0 [&>svg]:text-[#99a1af] gap-1 text-sm">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent align="start" className="rounded-xl shadow-lg border-[#f3f4f6]">
                            {availableMonths.map(m => (
                                <SelectItem key={m} value={m} className="font-medium cursor-pointer rounded-lg m-1">
                                    {m === '전체' ? '전체' : `2024년 ${m}월`}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Transaction Groups */}
                <div className="flex flex-col gap-6 w-full mt-2">
                    {groupedTransactions.map(group => (
                        <div key={group.date} className="flex flex-col gap-3 w-full">
                            {/* Date Header */}
                            <h3 className="font-bold text-[#101828] text-sm px-1">
                                {group.date}
                            </h3>

                            {/* Items List */}
                            <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col rounded-xl shadow-[0_1px_2px_rgba(0,0,0,0.02)] overflow-hidden w-full">
                                {group.items.map((item, index) => (
                                    <div
                                        key={item.id}
                                        onClick={() => setSelectedTransaction(item)}
                                        className={`flex items-start justify-between p-4 w-full cursor-pointer hover:bg-slate-50 transition-colors ${index < group.items.length - 1 ? 'border-b border-[#f3f4f6]' : ''
                                            }`}
                                    >
                                        <div className="flex flex-col gap-1">
                                            <p className="font-bold text-[#101828] text-[15px]">
                                                {item.description}
                                                {item.quantity !== undefined && item.quantity > 0 && (item.type.toLowerCase() === 'buy' || item.type.toLowerCase() === 'sell') && (
                                                    <span className="text-[#101828] font-bold text-[15px] ml-1">{item.quantity}주</span>
                                                )}
                                            </p>
                                            <div className="flex items-center gap-2 text-sm text-[#6a7282]">
                                                <span>{item.time}</span>
                                                <span className="text-[#d1d5db]">|</span>
                                                <span>{item.type.toLowerCase() === 'buy' ? '구매' : item.type.toLowerCase() === 'sell' ? '판매' : item.type.toLowerCase() === 'deposit' ? '입금' : '출금'}</span>
                                            </div>
                                        </div>

                                        <div className="flex flex-col items-end gap-1">
                                            <p className="font-bold text-base text-right text-[#101828]">
                                                {item.amount > 0 ? '+' : ''}{formatCurrency(item.amount)}
                                            </p>
                                            <p className="text-sm text-right text-[#99a1af]">
                                                {formatCurrency(item.remainingBalance)}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

            </div>

            {/* Detail Modal Layer */}
            <HistoryDetailModal isOpen={!!selectedTransaction} onClose={() => setSelectedTransaction(null)}>
                {selectedTransaction && (
                    <TransactionDetail
                        transaction={selectedTransaction}
                        onClose={() => setSelectedTransaction(null)}
                    />
                )}
            </HistoryDetailModal>

        </div>
    );
};
