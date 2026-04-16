import { useEffect, useMemo, useState } from "react";
import { useAccountStore } from "../../store/useAccountStore";
import { Button } from "@/components/ui/button";
import { Send, AlertCircle } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const AssetTab = () => {
    const {
        totalAssets,
        cashBalance,
        totalInvested,
        totalEvaluated,
        transactions,
        currentAccountType,
        fetchBalance, 
        fetchPositions, 
        fetchTransactions,
        transferFunds
        } = useAccountStore();

        const [isTransferOpen, setIsTransferOpen] = useState(false);
        const [transferAmount, setTransferAmount] = useState("");
        const [error, setError] = useState<string | null>(null);
        const [isPending, setIsPending] = useState(false);

        useEffect(() => {
        fetchBalance();
        fetchPositions();
        fetchTransactions({ size: 500 });

        const interval = setInterval(() => {
            fetchPositions();
        }, 1000);

        return () => clearInterval(interval);
        }, [fetchBalance, fetchPositions, fetchTransactions]);

        // 송금 금액 입력 핸들러 및 검증
        const handleAmountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        // 숫자가 아닌 문자 제거
        const rawValue = e.target.value.replace(/[^0-9]/g, "");

        // 콤마가 포함된 포맷팅된 문자열 생성
        const formattedValue = rawValue ? Number(rawValue).toLocaleString() : "";
        setTransferAmount(formattedValue);

        // 유효성 검사 (숫자 값으로 비교)
        if (rawValue && Number(rawValue) > cashBalance) {
            setError(`잔액이 부족합니다. (최대 ${formatCurrency(cashBalance)})`);
        } else {
            setError(null);
        }
        };

        // 송금 실행
        const handleTransfer = async () => {
        const rawAmount = Number(transferAmount.replace(/,/g, ""));
        if (!rawAmount || error || isPending) return;

        try {
            setIsPending(true);
            await transferFunds(rawAmount);
            setIsTransferOpen(false);
            setTransferAmount("");
        } catch (err) {
            console.error("Transfer failed:", err);
            setError("송금에 실패했습니다. 잠시 후 다시 시도해주세요.");
        } finally {
            setIsPending(false);
        }
        };
    // 실시간 평가 손익 및 수익률 계산
    const unrealizedProfit = totalEvaluated - totalInvested;
    const unrealizedReturnRate = totalInvested > 0 ? (unrealizedProfit / totalInvested) * 100 : 0;

    // 실현 손익 계산
    const currentMonth = new Date().getMonth() + 1;
    const monthlyRealizedProfit = useMemo(() => {
        const currentMonthStr = currentMonth.toString();
        const costBasisMap: Record<string, { qty: number; totalCost: number }> = {};
        let realizedProfit = 0;

        const sortedTransactions = [...transactions].reverse();

        sortedTransactions.forEach(t => {
            if (!t.stockName || !t.quantity) return;

            if (!costBasisMap[t.stockName]) {
                costBasisMap[t.stockName] = { qty: 0, totalCost: 0 };
            }
            const record = costBasisMap[t.stockName];

            if (t.type === 'buy') {
                record.qty += t.quantity;
                record.totalCost += Math.abs(t.amount);
            } else if (t.type === 'sell' && record.qty > 0) {
                const avgPrice = record.totalCost / record.qty;
                const profit = t.amount - (avgPrice * t.quantity);

                if (t.date.split('.')[0] === currentMonthStr) {
                    realizedProfit += profit;
                }

                record.qty -= t.quantity;
                record.totalCost -= (avgPrice * t.quantity);
            }
        });

        return realizedProfit;
    }, [transactions, currentMonth]);

    // 금액 포맷
    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('ko-KR').format(Math.round(value)) + '원';
    };

    // 수익 양수/음수 판별  
    const isPositiveUnrealized = unrealizedProfit >= 0;
    const isPositiveMonthly = monthlyRealizedProfit >= 0;

    // 대상 계좌 라벨
    const targetAccountLabel = currentAccountType === 'USER' ? 'AI계좌' : '기본계좌';

    return (
        <div className="flex-[1] min-w-0 relative flex flex-col pt-6 px-12 md:px-24 max-w-5xl mx-auto w-full h-full overflow-y-auto">
            <div className="flex flex-col gap-6 pb-12">

                {/* 1. Account Info & Cash Balance Card */}
                <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col gap-6 p-6 rounded-2xl shadow-sm w-full">
                    <div className="flex items-start justify-between w-full">
                        <div className="flex flex-col gap-1 w-full text-left">
                            <p className="text-[#6a7282] text-xs">
                                {currentAccountType === 'USER' ? '기본계좌' : 'AI계좌'}
                            </p>
                            <p className="font-bold text-[#101828] text-3xl md:text-4xl">
                                {formatCurrency(totalAssets)}
                            </p>
                        </div>

                        {/* 송금 모달 다이얼로그 */}
                        <Dialog open={isTransferOpen} onOpenChange={setIsTransferOpen}>
                            <DialogTrigger asChild>
                                <Button variant="secondary" size="sm" className="bg-[#f2f4f7] hover:bg-[#e4e7eb] text-[#475467] font-bold gap-1.5 h-9 rounded-xl shrink-0">
                                    <Send size={14} />
                                    보내기
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="sm:max-w-[425px] rounded-2xl">
                                <DialogHeader>
                                    <DialogTitle className="text-xl font-bold text-[#101828]">계좌 간 송금</DialogTitle>
                                    <DialogDescription className="text-sm text-[#6a7282]">
                                        내 계좌 간에 즉시 예수금을 이체합니다.
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="grid gap-6 py-6">
                                    <div className="flex flex-col gap-3">
                                        <Label htmlFor="amount" className="text-sm font-bold text-[#101828]">
                                            {targetAccountLabel}에 보낼 금액
                                        </Label>
                                        <div className="relative">
                                            <Input
                                                id="amount"
                                                type="text"
                                                placeholder="보낼 금액을 입력하세요"
                                                value={transferAmount}
                                                onChange={handleAmountChange}
                                                className={`h-12 text-lg font-bold pr-10 rounded-xl border-slate-200 focus:border-slate-400 focus:shadow-sm transition-all ${error ? 'border-red-500 focus:border-red-500' : ''}`}
                                            />
                                            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[#99a1af] font-bold">원</span>
                                        </div>
                                        <div className="flex justify-between items-center px-1">
                                            <span className={`text-[12px] font-medium transition-colors ${error ? 'text-red-500' : 'text-[#99a1af]'}`}>
                                                주문 가능 금액: {formatCurrency(cashBalance)}
                                            </span>
                                            {error && (
                                                <div className="flex items-center gap-1 text-red-500 animate-in fade-in slide-in-from-right-1">
                                                    <AlertCircle size={12} />
                                                    <span className="text-[11px] font-bold">잔액이 부족합니다</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button
                                        onClick={handleTransfer}
                                        disabled={!transferAmount || Number(transferAmount.replace(/,/g, "")) <= 0 || !!error}
                                        className="w-full h-12 rounded-xl bg-[#155dfc] hover:bg-[#0047e1] text-white font-bold transition-all disabled:opacity-50 disabled:bg-slate-200 disabled:text-slate-400"
                                    >
                                        {formatCurrency(Number(transferAmount.replace(/,/g, "") || 0))} 보내기
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>

                    <div className="bg-[#f9fafb] flex flex-col gap-1 p-4 rounded-xl w-full">
                        <p className="text-[#6a7282] text-xs">총 주문 가능 금액</p>
                        <p className="font-bold text-[#101828] text-lg">
                            {formatCurrency(cashBalance)}
                        </p>
                    </div>
                </div>

                {/* 2. Total Investment Card (Real-time Evaluation) */}
                <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col gap-4 p-6 rounded-2xl shadow-sm w-full">
                    <h3 className="font-bold text-[#101828] text-sm md:text-base">총 투자 및 실시간 평가</h3>

                    <div className="flex items-end justify-between w-full">
                        <div className="flex flex-col gap-1">
                            <p className="font-bold text-[#101828] text-2xl md:text-3xl">
                                {formatCurrency(totalEvaluated)}
                            </p>
                        </div>

                        <div className="flex flex-col items-end">
                            <p className={`font-bold text-base text-right ${isPositiveUnrealized ? 'text-[#fb2c36]' : 'text-[#2b7fff]'}`}>
                                {isPositiveUnrealized ? '+' : ''}{formatCurrency(unrealizedProfit)}
                            </p>
                            <p className={`text-xs text-right font-medium ${isPositiveUnrealized ? 'text-[#fb2c36]' : 'text-[#2b7fff]'}`}>
                                {isPositiveUnrealized ? '+' : ''}{unrealizedReturnRate.toFixed(2)}%
                            </p>
                        </div>
                    </div>
                </div>

                {/* 3. Detailed Realized Profit Card */}
                <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col gap-5 p-6 rounded-2xl shadow-sm w-full">
                    <h3 className="font-bold text-[#101828] text-sm md:text-base">수익 현황</h3>

                    <div className="w-full">
                        <div className="bg-[#f9fafb] flex flex-col gap-3 p-6 rounded-2xl">
                            <div className="flex justify-between items-start">
                                <p className="text-[#6a7282] text-xs font-semibold">{currentMonth}월 수익</p>
                            </div>
                            <div className="flex items-baseline gap-2 mt-1">
                                <p className={`font-bold text-3xl ${isPositiveMonthly && monthlyRealizedProfit !== 0 ? 'text-[#fb2c36]' : monthlyRealizedProfit < 0 ? 'text-[#2b7fff]' : 'text-[#101828]'}`}>
                                    {monthlyRealizedProfit > 0 ? '+' : ''}{formatCurrency(monthlyRealizedProfit)}
                                </p>
                            </div>
                            <p className="text-[#99a1af] text-[10px] mt-4 leading-relaxed">
                                * 이번 달에 완료된 매도 거래의 이익/손실 합계입니다.<br />
                                * 최근 500건의 매매 데이터를 분석하며, 장기 보유 종목 매도 시 평단가 계산에 오차가 있을 수 있습니다.
                            </p>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
};
