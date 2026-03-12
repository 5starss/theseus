import { useEffect } from "react";
import { useAccountStore } from "../../store/useAccountStore";

export const AssetTab = () => {
    const { totalAssets, cashBalance, totalInvested, totalEvaluated, fetchBalance, fetchPositions } = useAccountStore();

    useEffect(() => {
        fetchBalance();
        fetchPositions();

        // 1초마다 시세 갱신을 위해 포지션 정보 다시 가져오기
        const interval = setInterval(() => {
            fetchPositions();
        }, 1000);

        return () => clearInterval(interval);
    }, [fetchBalance, fetchPositions]);

    // 수익 및 수익률 계산
    const profit = totalEvaluated - totalInvested;
    const returnRate = totalInvested > 0 ? (profit / totalInvested) * 100 : 0;

    // 금액 포맷
    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('ko-KR').format(Math.round(value)) + '원';
    };

    // 수익 양수/음수 판별  
    const isPositive = profit >= 0;

    return (
        <div className="flex-[1] min-w-0 relative flex flex-col pt-6 px-12 md:px-24 max-w-5xl mx-auto w-full h-full overflow-y-auto">
            <div className="flex flex-col gap-6 pb-12">

                {/* 1. Account Info & Cash Balance Card */}
                <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col gap-6 p-6 rounded-2xl shadow-sm w-full">
                    <div className="flex items-center justify-between w-full">
                        <div className="flex flex-col gap-1 w-full">
                            <p className="text-[#6a7282] text-xs">
                                기본계좌 <span className="text-[#99a1af]">130-01-061715</span>
                            </p>
                            <p className="font-bold text-[#101828] text-3xl md:text-4xl">
                                {formatCurrency(totalAssets)}
                            </p>
                        </div>
                    </div>

                    <div className="bg-[#f9fafb] flex flex-col gap-1 p-4 rounded-xl w-full">
                        <p className="text-[#6a7282] text-xs">총 주문 가능 금액</p>
                        <p className="font-bold text-[#101828] text-lg">
                            {formatCurrency(cashBalance)}
                        </p>
                    </div>
                </div>

                {/* 2. Total Investment Card */}
                <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col gap-4 p-6 rounded-2xl shadow-sm w-full">
                    <h3 className="font-bold text-[#101828] text-sm">총 투자 금액</h3>

                    <div className="flex items-end justify-between w-full">
                        <div className="flex flex-col gap-1">
                            <p className="font-bold text-[#101828] text-2xl md:text-3xl">
                                {formatCurrency(totalEvaluated)}
                            </p>
                        </div>

                        <div className="flex flex-col items-end">
                            <p className={`font-bold text-sm text-right ${isPositive ? 'text-[#fb2c36]' : 'text-[#2b7fff]'}`}>
                                {isPositive ? '+' : ''}{formatCurrency(profit)}
                            </p>
                            <p className={`text-xs text-right ${isPositive ? 'text-[#fb2c36]' : 'text-[#2b7fff]'}`}>
                                {isPositive ? '+' : ''}{returnRate.toFixed(2)}%
                            </p>
                        </div>
                    </div>
                </div>

                {/* 3. Recent Profit Card */}
                <div className="bg-white border-[#f3f4f6] border-[0.5px] border-solid flex flex-col gap-4 p-6 rounded-2xl shadow-sm w-full">
                    <h3 className="font-bold text-[#101828] text-sm">수익 현황</h3>

                    <div className="bg-[#f9fafb] flex flex-col gap-2 p-4 rounded-xl w-full">
                        <p className="text-[#6a7282] text-xs">2일 수익</p>
                        <p className="font-bold text-[#2b7fff] text-lg">
                            -9,986원
                        </p>
                    </div>
                </div>

            </div>
        </div>
    );
};
