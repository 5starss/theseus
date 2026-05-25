import type { PortfolioHoldingItem } from "../../types/portfolio";

const CHART_COLORS = [
    "var(--color-chart-1)",
    "var(--color-chart-2)",
    "var(--color-chart-3)",
    "var(--color-chart-4)",
    "var(--color-chart-5)",
    "#155dfc",
    "#0f766e",
    "#f97316",
];

interface PortfolioDonutChartProps {
    items: PortfolioHoldingItem[];
    totalEvaluationAmount: number;
    formatCurrency: (value: number) => string;
}

export function PortfolioDonutChart({
    items,
    totalEvaluationAmount,
    formatCurrency,
}: PortfolioDonutChartProps) {
    const chartItems = items.filter((item) => item.portfolioWeight > 0);
    const radius = 78;
    const strokeWidth = 28;
    const normalizedRadius = radius - strokeWidth / 2;
    const circumference = normalizedRadius * 2 * Math.PI;

    let cumulativeWeight = 0;

    return (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,280px)_1fr] items-center">
            <div className="flex items-center justify-center">
                {chartItems.length === 0 ? (
                    <div className="flex h-[220px] w-[220px] items-center justify-center rounded-full border border-dashed border-slate-200 bg-slate-50 text-sm font-medium text-slate-400">
                        보유 종목 없음
                    </div>
                ) : (
                    <div className="relative h-[220px] w-[220px]">
                        <svg className="h-full w-full -rotate-90" viewBox="0 0 180 180">
                            <circle
                                cx="90"
                                cy="90"
                                r={normalizedRadius}
                                fill="transparent"
                                stroke="#e5e7eb"
                                strokeWidth={strokeWidth}
                            />
                            {chartItems.map((item, index) => {
                                const fraction = item.portfolioWeight / 100;
                                const dashLength = circumference * fraction;
                                const dashOffset = circumference * (1 - cumulativeWeight / 100);
                                cumulativeWeight += item.portfolioWeight;

                                return (
                                    <circle
                                        key={item.stockCode}
                                        cx="90"
                                        cy="90"
                                        r={normalizedRadius}
                                        fill="transparent"
                                        stroke={CHART_COLORS[index % CHART_COLORS.length]}
                                        strokeWidth={strokeWidth}
                                        strokeDasharray={`${dashLength} ${circumference - dashLength}`}
                                        strokeDashoffset={dashOffset}
                                        strokeLinecap="butt"
                                    />
                                );
                            })}
                        </svg>
                        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                                총 평가금액
                            </span>
                            <strong className="mt-2 px-5 text-xl font-bold leading-tight text-slate-900">
                                {formatCurrency(totalEvaluationAmount)}
                            </strong>
                        </div>
                    </div>
                )}
            </div>

            <div className="grid gap-3">
                {chartItems.map((item, index) => (
                    <div
                        key={item.stockCode}
                        className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50/80 px-4 py-3"
                    >
                        <div className="flex min-w-0 items-center gap-3">
                            <span
                                className="h-3 w-3 shrink-0 rounded-full"
                                style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                            />
                            <div className="min-w-0">
                                <p className="truncate text-sm font-bold text-slate-900">{item.stockName}</p>
                                <p className="text-xs text-slate-500">{item.stockCode}</p>
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="text-sm font-bold text-slate-900">{item.portfolioWeight.toFixed(2)}%</p>
                            <p className="text-xs text-slate-500">{formatCurrency(item.evaluationAmount)}</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
