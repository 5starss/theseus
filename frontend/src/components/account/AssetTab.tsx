import { useCallback, useEffect, useMemo, useState } from "react";
import { useAccountStore } from "../../store/useAccountStore";
import { Button } from "@/components/ui/button";
import { AlertCircle, ArrowDownWideNarrow, PieChart, Send, TrendingDown, TrendingUp } from "lucide-react";
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
import { portfolioApi } from "../../api/portfolio";
import { PortfolioDonutChart } from "./PortfolioDonutChart";
import type {
    PortfolioFilterType,
    PortfolioHoldingItem,
    PortfolioSortType,
    PortfolioSummaryResponse,
} from "../../types/portfolio";

export const AssetTab = () => {
    const {
        cashBalance,
        transactions,
        currentAccountType,
        fetchBalance, 
        fetchTransactions,
        transferFunds
        } = useAccountStore();

    const [isTransferOpen, setIsTransferOpen] = useState(false);
    const [transferAmount, setTransferAmount] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isPending, setIsPending] = useState(false);
    const [summary, setSummary] = useState<PortfolioSummaryResponse | null>(null);
    const [isSummaryLoading, setIsSummaryLoading] = useState(true);
    const [summaryError, setSummaryError] = useState<string | null>(null);
    const [filter, setFilter] = useState<PortfolioFilterType>("all");
    const [sort, setSort] = useState<PortfolioSortType>("evaluation");

    const loadSummary = useCallback(async () => {
        try {
            setSummaryError(null);
            const response = await portfolioApi.getMySummary();
            setSummary(response);
        } catch (loadError) {
            console.error("Failed to fetch portfolio summary:", loadError);
            setSummaryError("포트폴리오 요약을 불러오지 못했습니다.");
        } finally {
            setIsSummaryLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchBalance();
        fetchTransactions({ size: 500 });
        loadSummary();

        const interval = setInterval(() => {
            loadSummary();
        }, 5000);

        return () => clearInterval(interval);
    }, [fetchBalance, fetchTransactions, loadSummary]);

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

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('ko-KR', {
            style: 'currency',
            currency: 'KRW',
            maximumFractionDigits: 0,
        }).format(Math.round(value));
    };

    const isPositiveMonthly = monthlyRealizedProfit >= 0;

    const targetAccountLabel = currentAccountType === 'USER' ? 'AI계좌' : '기본계좌';

    const filteredItems = useMemo(() => {
        const items = summary?.items ?? [];

        const visibleItems = items.filter((item) => {
            if (filter === "profit") {
                return item.profitLoss > 0;
            }
            if (filter === "loss") {
                return item.profitLoss < 0;
            }
            return true;
        });

        const sortedItems = [...visibleItems].sort((a, b) => {
            switch (sort) {
                case "profitRate":
                    return b.profitRate - a.profitRate || b.evaluationAmount - a.evaluationAmount;
                case "weight":
                    return b.portfolioWeight - a.portfolioWeight || b.evaluationAmount - a.evaluationAmount;
                case "name":
                    return a.stockName.localeCompare(b.stockName, "ko-KR");
                case "evaluation":
                default:
                    return b.evaluationAmount - a.evaluationAmount || b.portfolioWeight - a.portfolioWeight;
            }
        });

        return sortedItems;
    }, [filter, sort, summary?.items]);

    const summaryCards = summary ? [
        { label: "총 평가금액", value: formatCurrency(summary.totalEvaluationAmount), tone: "text-slate-900" },
        { label: "총 매수금액", value: formatCurrency(summary.totalPurchaseAmount), tone: "text-slate-900" },
        {
            label: "총 평가손익",
            value: `${summary.totalProfitLoss >= 0 ? "+" : ""}${formatCurrency(summary.totalProfitLoss)}`,
            tone: summary.totalProfitLoss >= 0 ? "text-rose-500" : "text-blue-600",
        },
        {
            label: "총 수익률",
            value: `${summary.totalProfitRate >= 0 ? "+" : ""}${summary.totalProfitRate.toFixed(2)}%`,
            tone: summary.totalProfitRate >= 0 ? "text-rose-500" : "text-blue-600",
        },
        { label: "보유 종목 수", value: `${summary.holdingCount}개`, tone: "text-slate-900" },
    ] : [];

    const filterOptions: Array<{ key: PortfolioFilterType; label: string }> = [
        { key: "all", label: "전체" },
        { key: "profit", label: "수익중" },
        { key: "loss", label: "손실중" },
    ];

    const sortOptions: Array<{ key: PortfolioSortType; label: string }> = [
        { key: "evaluation", label: "평가금액순" },
        { key: "profitRate", label: "수익률순" },
        { key: "weight", label: "비중순" },
        { key: "name", label: "종목명순" },
    ];

    const renderHoldingCard = (item: PortfolioHoldingItem) => {
        const isProfit = item.profitLoss >= 0;

        return (
            <article
                key={item.stockCode}
                className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
            >
                <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                        <h4 className="truncate text-lg font-bold text-slate-900">{item.stockName}</h4>
                        <p className="mt-1 text-xs font-medium tracking-[0.18em] text-slate-400">{item.stockCode}</p>
                    </div>
                    <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
                        비중 {item.portfolioWeight.toFixed(2)}%
                    </div>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <div>
                        <p className="text-xs font-medium text-slate-400">보유 수량</p>
                        <p className="mt-1 text-sm font-bold text-slate-900">{item.quantity.toLocaleString()}주</p>
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-400">평균 매수가</p>
                        <p className="mt-1 text-sm font-bold text-slate-900">{formatCurrency(item.averagePurchasePrice)}</p>
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-400">현재가</p>
                        <p className="mt-1 text-sm font-bold text-slate-900">{formatCurrency(item.currentPrice)}</p>
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-400">총 매수금액</p>
                        <p className="mt-1 text-sm font-bold text-slate-900">{formatCurrency(item.purchaseAmount)}</p>
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-400">평가금액</p>
                        <p className="mt-1 text-sm font-bold text-slate-900">{formatCurrency(item.evaluationAmount)}</p>
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-400">평가손익</p>
                        <p className={`mt-1 text-sm font-bold ${isProfit ? "text-rose-500" : "text-blue-600"}`}>
                            {item.profitLoss >= 0 ? "+" : ""}{formatCurrency(item.profitLoss)}
                        </p>
                    </div>
                </div>

                <div className="mt-5 flex items-center justify-between rounded-2xl bg-slate-50 px-4 py-3">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                        {isProfit ? <TrendingUp size={16} className="text-rose-500" /> : <TrendingDown size={16} className="text-blue-600" />}
                        수익률
                    </div>
                    <p className={`text-base font-bold ${isProfit ? "text-rose-500" : "text-blue-600"}`}>
                        {item.profitRate >= 0 ? "+" : ""}{item.profitRate.toFixed(2)}%
                    </p>
                </div>
            </article>
        );
    };

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
                                {formatCurrency(cashBalance + (summary?.totalEvaluationAmount ?? 0))}
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

                <div className="rounded-[28px] border border-slate-100 bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 p-6 text-white shadow-sm">
                    <div className="flex items-center justify-between gap-3">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-200/70">
                                Portfolio Dashboard
                            </p>
                            <h3 className="mt-2 text-2xl font-bold">내 포트폴리오</h3>
                        </div>
                        <PieChart className="h-8 w-8 text-blue-300" />
                    </div>
                    {isSummaryLoading ? (
                        <div className="mt-6 grid gap-3 md:grid-cols-5">
                            {Array.from({ length: 5 }).map((_, index) => (
                                <div key={index} className="rounded-2xl bg-white/8 px-4 py-5 animate-pulse">
                                    <div className="h-3 w-16 rounded bg-white/15" />
                                    <div className="mt-4 h-6 w-24 rounded bg-white/15" />
                                </div>
                            ))}
                        </div>
                    ) : summaryError ? (
                        <div className="mt-6 rounded-2xl border border-red-400/20 bg-red-500/10 px-5 py-4 text-sm text-red-100">
                            {summaryError}
                        </div>
                    ) : (
                        <div className="mt-6 grid gap-3 md:grid-cols-5">
                            {summaryCards.map((card) => (
                                <div key={card.label} className="rounded-2xl bg-white/8 px-4 py-5 backdrop-blur-sm">
                                    <p className="text-xs font-semibold text-blue-100/65">{card.label}</p>
                                    <p className={`mt-3 text-lg font-bold ${card.tone === "text-slate-900" ? "text-white" : card.tone.replace("text-", "text-")}`}>
                                        {card.value}
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {!isSummaryLoading && !summaryError && summary && summary.holdingCount > 0 && (
                    <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col gap-6 p-6 rounded-2xl shadow-sm w-full">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <h3 className="font-bold text-[#101828] text-base md:text-lg">자산 구성</h3>
                                <p className="mt-1 text-sm text-slate-500">보유 종목별 평가금액 비중</p>
                            </div>
                        </div>
                        <PortfolioDonutChart
                            items={summary.items}
                            totalEvaluationAmount={summary.totalEvaluationAmount}
                            formatCurrency={formatCurrency}
                        />
                    </div>
                )}

                <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col gap-5 p-6 rounded-2xl shadow-sm w-full">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                            <h3 className="font-bold text-[#101828] text-base md:text-lg">보유 종목 현황</h3>
                            <p className="mt-1 text-sm text-slate-500">수익 상태와 정렬 기준으로 종목을 빠르게 확인합니다.</p>
                        </div>
                        <div className="flex flex-col gap-3 md:flex-row md:items-center">
                            <div className="flex flex-wrap gap-2">
                                {filterOptions.map((option) => (
                                    <Button
                                        key={option.key}
                                        type="button"
                                        variant="outline"
                                        onClick={() => setFilter(option.key)}
                                        className={filter === option.key
                                            ? "rounded-full border-slate-900 bg-slate-900 text-white hover:bg-slate-900 hover:text-white"
                                            : "rounded-full border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}
                                    >
                                        {option.label}
                                    </Button>
                                ))}
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {sortOptions.map((option) => (
                                    <Button
                                        key={option.key}
                                        type="button"
                                        variant="ghost"
                                        onClick={() => setSort(option.key)}
                                        className={sort === option.key
                                            ? "rounded-full bg-blue-50 text-blue-700 hover:bg-blue-50"
                                            : "rounded-full text-slate-500 hover:bg-slate-100"}
                                    >
                                        <ArrowDownWideNarrow size={14} />
                                        {option.label}
                                    </Button>
                                ))}
                            </div>
                        </div>
                    </div>

                    {isSummaryLoading ? (
                        <div className="grid gap-4">
                            {Array.from({ length: 3 }).map((_, index) => (
                                <div key={index} className="rounded-2xl border border-slate-100 p-5 animate-pulse">
                                    <div className="h-4 w-24 rounded bg-slate-100" />
                                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                                        {Array.from({ length: 6 }).map((__, lineIndex) => (
                                            <div key={lineIndex} className="h-10 rounded bg-slate-100" />
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : summaryError ? (
                        <div className="rounded-2xl border border-red-100 bg-red-50 px-5 py-6 text-sm text-red-600">
                            {summaryError}
                        </div>
                    ) : !summary || summary.items.length === 0 ? (
                        <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 px-6 py-16 text-center">
                            <p className="text-base font-bold text-slate-700">보유 중인 종목이 없습니다.</p>
                            <p className="mt-2 text-sm text-slate-500">종목을 매수하면 이곳에서 포트폴리오 구성을 확인할 수 있습니다.</p>
                        </div>
                    ) : filteredItems.length === 0 ? (
                        <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 px-6 py-16 text-center">
                            <p className="text-base font-bold text-slate-700">조건에 맞는 종목이 없습니다.</p>
                            <p className="mt-2 text-sm text-slate-500">다른 필터를 선택해 전체 종목을 확인해보세요.</p>
                        </div>
                    ) : (
                        <div className="grid gap-4">
                            {filteredItems.map(renderHoldingCard)}
                        </div>
                    )}
                </div>

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
