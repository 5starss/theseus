import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useStockStore } from "../../store/useStockStore";
import { useAccountStore } from "../../store/useAccountStore";
import { useAuthStore } from "../../store/useAuthStore";
import { useNotificationStore } from "../../store/useNotificationStore";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { LoginGuardOverlay } from "./LoginGuardOverlay";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getTickSize } from "../../utils/priceUtils";

export function OrderPanel() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const navigate = useNavigate();
    const location = useLocation();
    const [orderType, setOrderType] = useState<"buy" | "sell">("buy");
    const isBuy = orderType === "buy";

    // 스토어에서 현재가, 종목명, 종목코드 가져오기
    const currentPrice = useStockStore(state => state.currentPrice);
    const stockName = useStockStore(state => state.stockName);
    const stockCode = useStockStore(state => state.stockCode);
    const selectedOrderPrice = useStockStore(state => state.selectedOrderPrice);

    const cashBalance = useAccountStore(state => state.cashBalance);
    const portfolio = useAccountStore(state => state.portfolio);
    const executeTrade = useAccountStore(state => state.executeTrade);

    // 주문 가격, 수량, 주문 확인 모달, 이전 종목코드
    const [orderPrice, setOrderPrice] = useState(currentPrice);
    const [quantity, setQuantity] = useState(0);
    const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
    const [prevStockCode, setPrevStockCode] = useState(stockCode);

    // 주식 종목이 바뀌거나 현재가가 로드될 때 주문 가격과 수량을 동기화
    useEffect(() => {
        if (stockCode !== prevStockCode) {
            setPrevStockCode(stockCode);
            setOrderPrice(0);
            setQuantity(0);
        } else if (orderPrice === 0 && currentPrice > 0) {
            setOrderPrice(currentPrice);
        }
    }, [stockCode, currentPrice, prevStockCode, orderPrice]);

    // 호가창에서 가격을 클릭한 경우 주문 가격 업데이트
    useEffect(() => {
        if (selectedOrderPrice > 0) {
            setOrderPrice(selectedOrderPrice);
        }
    }, [selectedOrderPrice]);

    // 매도 가능 수량 계산
    const selectedStock = portfolio.find(p => p.code === stockCode);
    const availableSharesCount = selectedStock?.availableShares || 0;

    // 주문 총액 계산
    const totalAmount = orderPrice * quantity;
    const canTrade = quantity > 0 && orderPrice > 0;

    // 구매/판매 최대 수량 계산
    const maxBuyQty = orderPrice > 0 ? Math.floor(cashBalance / orderPrice) : 0;
    const maxSellQty = availableSharesCount;

    // 구매/판매 가능 수량 계산
    const availableText = isBuy ? `${maxBuyQty.toLocaleString()}주` : `${maxSellQty.toLocaleString()}주`;

    const handleQuantityChange = (delta: number) => {
        setQuantity(prev => {
            const next = prev + delta;
            if (next < 0) return 0;
            if (isBuy && next > maxBuyQty) return maxBuyQty;
            if (!isBuy && next > maxSellQty) return maxSellQty;
            return next;
        });
    };

    const handleManualPriceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value.replace(/[^0-9]/g, '');
        setOrderPrice(val ? parseInt(val, 10) : 0);
    };

    const handleManualQuantityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value.replace(/[^0-9]/g, '');
        let next = val ? parseInt(val, 10) : 0;
        if (isBuy && next > maxBuyQty) next = maxBuyQty;
        if (!isBuy && next > maxSellQty) next = maxSellQty;
        setQuantity(next);
    };

    const handlePercentage = (percent: number) => {
        if (isBuy) {
            setQuantity(Math.floor(maxBuyQty * percent));
        } else {
            setQuantity(Math.floor(maxSellQty * percent));
        }
    };

    const handleConfirmTrade = async () => {
        if (!canTrade) return;

        try {
            await executeTrade({
                stockName,
                stockCode,
                quantity,
                price: orderPrice,
                type: orderType
            });

            // 주문 성공 알림 추가
            useNotificationStore.getState().addNotification({
                eventType: 'ORDER',
                orderType: orderType.toUpperCase() as 'BUY' | 'SELL',
                ticker: stockName,
                matchPrice: orderPrice,
                matchQuantity: quantity,
                executedAt: new Date().toISOString()
            });

            setIsConfirmModalOpen(false);
            setQuantity(0);
        } catch (error: any) {
            console.error("Trade execution failed:", error);
            alert(error.message || "주문에 실패했습니다. 다시 시도해주세요.");
        }
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex flex-col h-full relative">
            {/* Tabs */}
            <Tabs value={orderType} onValueChange={(val) => { setOrderType(val as "buy" | "sell"); setQuantity(0); }} className="mb-4">
                <TabsList className="w-full h-auto flex gap-2 bg-transparent p-0">
                    <TabsTrigger
                        value="buy"
                        className="flex-1 py-1.5 rounded-md text-sm font-bold transition-colors data-[state=active]:bg-[#fb2c36] data-[state=active]:text-white data-[state=active]:shadow-none bg-slate-100 text-slate-500 hover:bg-slate-200 shadow-none border-none"
                    >
                        구매
                    </TabsTrigger>
                    <TabsTrigger
                        value="sell"
                        className="flex-1 py-1.5 rounded-md text-sm font-bold transition-colors data-[state=active]:bg-[#155dfc] data-[state=active]:text-white data-[state=active]:shadow-none bg-slate-100 text-slate-500 hover:bg-slate-200 shadow-none border-none"
                    >
                        판매
                    </TabsTrigger>
                </TabsList>
            </Tabs>

            {/* Price and Quantity Form */}
            <div className="flex flex-col gap-3 flex-1">
                {/* Price */}
                <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-500 w-12">가격</span>
                    <div className="flex-1 flex items-center bg-slate-50 border border-slate-200 rounded-md p-1">
                        <Button
                            variant="ghost" size="icon"
                            onClick={() => setOrderPrice(prev => Math.max(0, prev - getTickSize(prev)))}
                            className="w-8 h-8 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded transition-colors"
                        >-</Button>
                        <input
                            type="text"
                            className="w-full bg-transparent text-right text-sm font-bold text-slate-700 outline-none px-2"
                            value={orderPrice === 0 ? '' : orderPrice.toLocaleString()}
                            onChange={handleManualPriceChange}
                            placeholder="0"
                        />
                        <Button
                            variant="ghost" size="icon"
                            onClick={() => setOrderPrice(prev => prev + getTickSize(prev))}
                            className="w-8 h-8 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded transition-colors"
                        >+</Button>
                    </div>
                </div>

                {/* Quantity */}
                <div className="flex items-center justify-between mt-1">
                    <span className="text-xs font-medium text-slate-500 w-12">수량</span>
                    <div className="flex-1">
                        <div className="flex justify-end mb-1">
                            <span className="text-[10px] text-slate-400">가능 {availableText}</span>
                        </div>
                        <div className="flex items-center bg-slate-50 border border-slate-200 rounded-md p-1">
                            <Button variant="ghost" size="icon" onClick={() => handleQuantityChange(-1)} className="w-8 h-8 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded transition-colors">-</Button>
                            <div className="flex flex-1 items-center justify-end px-2">
                                <input
                                    type="text"
                                    className="w-full bg-transparent text-right text-sm font-semibold outline-none"
                                    value={quantity === 0 ? '' : quantity.toLocaleString()}
                                    onChange={handleManualQuantityChange}
                                    placeholder="0"
                                />
                                <span className="text-sm font-semibold text-slate-700 ml-0.5 whitespace-nowrap">주</span>
                            </div>
                            <Button variant="ghost" size="icon" onClick={() => handleQuantityChange(1)} className="w-8 h-8 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded transition-colors">+</Button>
                        </div>
                        <div className="flex gap-1 mt-2">
                            <Button variant="secondary" onClick={() => handlePercentage(0.1)} className="flex-1 h-6 text-[10px] font-medium bg-slate-100 text-slate-600 rounded hover:bg-slate-200 transition-colors shadow-none px-0">10%</Button>
                            <Button variant="secondary" onClick={() => handlePercentage(0.5)} className="flex-1 h-6 text-[10px] font-medium bg-slate-100 text-slate-600 rounded hover:bg-slate-200 transition-colors shadow-none px-0">50%</Button>
                            <Button variant="secondary" onClick={() => handlePercentage(1)} className="flex-1 h-6 text-[10px] font-medium bg-slate-100 text-slate-600 rounded hover:bg-slate-200 transition-colors shadow-none px-0">최대</Button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Total Value */}
            {quantity > 0 && (
                <div className="mt-4 mb-2 flex justify-between items-center text-sm font-bold animate-in fade-in zoom-in duration-200">
                    <span className="text-slate-500">주문 금액</span>
                    <span className={isBuy ? 'text-[#ce242b]' : 'text-[#0e48c4]'}>{totalAmount.toLocaleString()}원</span>
                </div>
            )}

            {/* Submit Button */}
            {!isLoggedIn ? (
                <Button
                    onClick={() => navigate('/login', { state: { from: location } })}
                    className={`mt-4 w-full h-12 rounded-lg text-sm font-bold text-white transition-colors 
                    ${isBuy ? 'bg-[#fb2c36] hover:bg-[#e02730]' : 'bg-[#155dfc] hover:bg-[#124bc9]'}`}
                >
                    {isBuy ? "로그인하고 구매하기" : "로그인하고 판매하기"}
                </Button>
            ) : (
                <Button
                    onClick={() => canTrade && setIsConfirmModalOpen(true)}
                    className={`mt-4 w-full h-12 rounded-lg text-sm font-bold text-white transition-colors 
                    ${!canTrade ? 'bg-slate-300 pointer-events-none' : (isBuy ? 'bg-[#fb2c36] hover:bg-[#e02730]' : 'bg-[#155dfc] hover:bg-[#124bc9]')}`}
                    disabled={!canTrade}
                >
                    {isBuy ? "구매하기" : "판매하기"}
                </Button>
            )}

            {/* Confirmation Dialog */}
            <Dialog open={isConfirmModalOpen} onOpenChange={setIsConfirmModalOpen}>
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
                            <span className="text-xs font-medium text-slate-500 pl-1">예상 수수료</span>
                            <span className="text-sm font-bold text-slate-800 pr-1">0원</span>
                        </div>
                        <div className="h-px bg-slate-100 my-1 w-full relative">
                            <div className="absolute top-1/2 -translate-y-1/2 left-1/2 -translate-x-1/2 bg-[#f8fafc] w-6 h-6 flex items-center justify-center rounded-full border border-slate-100">
                                <span className="text-[16px] text-[#fb2c36] font-bold pb-1">=</span>
                            </div>
                        </div>
                        <div className="flex flex-col items-center mt-2 bg-[#f8fafc] p-4 rounded-xl border border-slate-100">
                            <span className="text-[11px] font-semibold text-slate-500 mb-1">총 주문 금액</span>
                            <span className={`text-xl font-bold ${isBuy ? 'text-[#ce242b]' : 'text-[#0e48c4]'}`}>
                                {totalAmount.toLocaleString()}원
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 mb-6 ml-1">
                        <div className="w-4 h-4 rounded border border-slate-300"></div>
                        <span className="text-[11px] text-slate-500 font-medium">다음부터 확인창 없이 거래하기</span>
                    </div>

                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            className="flex-1 py-6 bg-slate-100 border-none text-slate-500 font-bold hover:bg-slate-200 hover:text-slate-600 rounded-xl"
                            onClick={() => setIsConfirmModalOpen(false)}
                        >
                            취소
                        </Button>
                        <Button
                            className={`flex-1 py-6 text-white font-bold rounded-xl
                                ${isBuy ? 'bg-[#fb2c36] hover:bg-[#e02730]' : 'bg-[#155dfc] hover:bg-[#124bc9]'}`}
                            onClick={handleConfirmTrade}
                        >
                            {isBuy ? "구매" : "판매"}
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}

export function MyStockInfo() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const stockName = useStockStore(state => state.stockName);
    const currentPrice = useStockStore(state => state.currentPrice);

    const stockCode = useStockStore(state => state.stockCode);
    const portfolio = useAccountStore(state => state.portfolio);

    // 실제 보유 데이터 찾기
    const myHolding = portfolio.find(p => p.code === stockCode);
    const ownedShares = myHolding ? myHolding.shares : 0;
    const avgPrice = myHolding ? myHolding.avgPrice : 0;

    // 계산식 적용
    const totalValue = currentPrice * ownedShares;
    const totalProfit = ownedShares > 0 ? totalValue - (avgPrice * ownedShares) : 0;
    const profitRate = (ownedShares > 0 && avgPrice > 0) ? (totalProfit / (avgPrice * ownedShares)) * 100 : 0;
    const isProfit = totalProfit >= 0;

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 h-full flex flex-col relative overflow-hidden">
            {/* 로그인 필요 시 오버레이 */}
            {!isLoggedIn && <LoginGuardOverlay />}

            <div className={`flex flex-col h-full ${!isLoggedIn ? 'opacity-30 pointer-events-none blur-[2px]' : ''}`}>
                <div className="flex justify-between items-end mb-4 pr-1">
                    <h3 className="font-bold text-slate-800">내 주식</h3>
                    <span className="text-xs font-medium text-slate-500">{stockName}</span>
                </div>

                <div className="flex flex-col gap-2.5">
                    <div className="flex justify-between items-center bg-slate-50 px-3 py-2 rounded-md">
                        <span className="text-xs font-semibold text-slate-500">보유수량</span>
                        <span className="text-sm font-bold text-slate-800">{ownedShares.toLocaleString()}주</span>
                    </div>
                    <div className="flex justify-between items-center bg-slate-50 px-3 py-2 rounded-md">
                        <span className="text-xs font-semibold text-slate-500">평가금액</span>
                        <span className="text-sm font-bold text-slate-800">{totalValue.toLocaleString()}</span>
                    </div>

                    <div className="h-px w-full bg-slate-100 my-1"></div>

                    <div className="flex justify-between items-center">
                        <span className="text-[11px] font-medium text-slate-500 pl-1">평가손익</span>
                        <span className={`text-xs font-bold pr-1 ${isProfit ? 'text-red-500' : 'text-blue-500'}`}>
                            {isProfit ? '+' : ''}{totalProfit.toLocaleString()}
                        </span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-[11px] font-medium text-slate-500 pl-1">수익률</span>
                        <span className={`text-xs font-bold pr-1 ${isProfit ? 'text-red-500' : 'text-blue-500'}`}>
                            {isProfit ? '+' : ''}{profitRate.toFixed(2)}%
                        </span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-[11px] font-medium text-slate-500 pl-1">1주 평균 금액</span>
                        <span className="text-xs font-semibold text-slate-700 pr-1">{avgPrice.toLocaleString()}</span>
                    </div>
                </div>
            </div>
        </div>
    );
}

export function MyOrderHistory() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const navigate = useNavigate();
    const [tab, setTab] = useState<"pending" | "completed">("completed");

    const pendingOrders = useAccountStore(state => state.pendingOrders);
    const completedOrders = useAccountStore(state => state.completedOrders);
    const fetchPendingOrders = useAccountStore(state => state.fetchPendingOrders);
    const fetchCompletedOrders = useAccountStore(state => state.fetchCompletedOrders);
    const stockCode = useStockStore(state => state.stockCode);

    // 현재 종목의 주문 내역만 필터링
    const stockOrders = [...pendingOrders, ...completedOrders].filter((o: any) => o.stockCode === stockCode);

    const currentOrders = tab === "pending"
        ? stockOrders.filter((o: any) => o.status === 'pending')
        : stockOrders.filter((o: any) => o.status !== 'pending');

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 h-full flex flex-col relative overflow-hidden">
            {/* 로그인 필요 시 오버레이 */}
            {!isLoggedIn && <LoginGuardOverlay />}

            <div className={`flex flex-col h-full ${!isLoggedIn ? 'opacity-30 pointer-events-none blur-[2px]' : ''}`}>
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-slate-800">나의 주문내역</h3>
                    <Button variant="ghost" onClick={() => navigate('/account/orders')} className="h-6 px-2 text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors">더보기</Button>
                </div>

                <Tabs
                    value={tab}
                    onValueChange={(val) => {
                        setTab(val as "pending" | "completed");
                        if (val === "pending") fetchPendingOrders();
                        else fetchCompletedOrders({ ticker: stockCode });
                    }}
                    className="mb-4"
                >
                    <TabsList className="w-full h-auto flex gap-2 bg-transparent p-0">
                        <TabsTrigger
                            value="pending"
                            className="flex-1 py-1.5 rounded-md text-xs font-bold transition-colors data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=active]:shadow-none bg-slate-100 text-slate-500 hover:bg-slate-200 shadow-none border-none"
                        >
                            대기
                        </TabsTrigger>
                        <TabsTrigger
                            value="completed"
                            className="flex-1 py-1.5 rounded-md text-xs font-bold transition-colors data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=active]:shadow-none bg-slate-100 text-slate-500 hover:bg-slate-200 shadow-none border-none"
                        >
                            완료
                        </TabsTrigger>
                    </TabsList>
                </Tabs>

                <div className="flex-1 overflow-y-auto pr-1">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="border-b border-slate-200">
                                {tab === "completed" && <th className="pb-2 text-xs font-semibold text-slate-500 w-[20%] text-center">일자</th>}
                                <th className={`pb-2 text-xs font-semibold text-slate-500 ${tab === "pending" ? "w-[20%]" : "w-[20%]"} text-center`}>구분</th>
                                <th className={`pb-2 text-xs font-semibold text-slate-500 ${tab === "pending" ? "w-[30%]" : "w-[35%]"} text-center`}>단가</th>
                                <th className={`pb-2 text-xs font-semibold text-slate-500 ${tab === "pending" ? "w-[20%]" : "w-[25%]"} text-center`}>수량</th>
                                {tab === "pending" && <th className="pb-2 text-xs font-semibold text-slate-500 w-[30%] text-center">관리</th>}
                            </tr>
                        </thead>
                        <tbody>
                            {currentOrders.length === 0 ? (
                                <tr><td colSpan={tab === "pending" ? 4 : 4} className="py-4 text-center text-xs text-slate-400">내역이 없습니다.</td></tr>
                            ) : (
                                currentOrders.map((order: any, idx: number) => (
                                    <tr key={idx} className="border-b border-slate-50 last:border-none hover:bg-slate-50/50 transition-colors">
                                        {tab === "completed" && (
                                            <td className="py-2.5 text-xs font-medium text-slate-500 text-center">{order.date}</td>
                                        )}
                                        <td className={`py-2.5 text-xs font-bold text-center ${order.status === 'canceled' || order.status === 'canceling' ? 'text-slate-400' : order.type === 'buy' ? 'text-red-500' : 'text-blue-500'}`}>
                                            {order.status === 'canceled'
                                                ? (order.type === 'buy' ? '매수취소' : '매도취소')
                                                : order.status === 'canceling'
                                                    ? (order.type === 'buy' ? '매수취소중' : '매도취소중')
                                                    : order.type === 'buy' ? '매수' : '매도'}
                                        </td>
                                        <td className="py-2.5 text-xs font-semibold text-slate-700 text-center">{order.price.toLocaleString()}</td>
                                        <td className="py-2.5 text-xs font-medium text-slate-600 text-center">{order.quantity}주</td>
                                        {tab === "pending" && (
                                            <td className="py-2.5">
                                                <div className="flex items-center justify-center gap-1">
                                                    {order.status === 'canceling' ? (
                                                        <span className="text-slate-400 font-medium text-[10px] px-2 py-1">취소중</span>
                                                    ) : (
                                                        <>
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); /* TODO: 수정 기능 */ }}
                                                                className="bg-slate-100 text-slate-600 font-medium text-[10px] px-2 py-1 rounded hover:bg-slate-200 transition-colors"
                                                            >
                                                                수정
                                                            </button>
                                                            <button
                                                                onClick={async (e) => {
                                                                    e.stopPropagation();
                                                                    if (window.confirm("정말 주문을 취소하시겠습니까?")) {
                                                                        try {
                                                                            await useAccountStore.getState().cancelOrder(order.id);
                                                                            setTab("completed");
                                                                        } catch (error: any) {
                                                                            alert(error.message || "주문 취소에 실패했습니다.");
                                                                        }
                                                                    }
                                                                }}
                                                                className="bg-slate-100 text-slate-600 font-medium text-[10px] px-2 py-1 rounded hover:bg-slate-200 transition-colors"
                                                            >
                                                                취소
                                                            </button>
                                                        </>
                                                    )}
                                                </div>
                                            </td>
                                        )}
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
