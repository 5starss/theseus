import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useStockStore } from "../../../store/useStockStore";
import { useAccountStore } from "../../../store/useAccountStore";
import { useAuthStore } from "../../../store/useAuthStore";
import { useNotificationStore } from "../../../store/useNotificationStore";
import { useConfigStore } from "../../../store/useConfigStore";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { useOrderForm } from "./useOrderForm";
import { ConfirmOrderModal } from "./ConfirmOrderModal";

export function OrderPanel() {
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const navigate = useNavigate();
    const location = useLocation();
    const [orderType, setOrderType] = useState<"buy" | "sell">("buy");
    const isBuy = orderType === "buy";

    const stockName = useStockStore(state => state.stockName);
    const stockCode = useStockStore(state => state.stockCode);
    const executeTrade = useAccountStore(state => state.executeTrade);
    const feeRate = useConfigStore(state => state.feeRate);
    const taxRate = useConfigStore(state => state.taxRate);

    const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);

    const {
        orderPrice,
        quantity,
        setQuantity,
        maxQty,
        totalAmount,
        fee,
        tax,
        totalWithFeeAndTax,
        handlePriceChange,
        handleManualPriceChange,
        handleQuantityChange,
        handleManualQuantityChange,
        handlePercentage
    } = useOrderForm(orderType);

    const canTrade = quantity > 0 && orderPrice > 0;

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
        } catch (err) {
            const error = err as Error;
            console.error("Trade execution failed:", error);
            toast.error(error.message || "주문에 실패했습니다. 다시 시도해주세요.");
        }
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex flex-col h-full relative">
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

            <div className="flex flex-col gap-3 flex-1">
                <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-500 w-12">가격</span>
                    <div className="flex-1 flex items-center bg-slate-50 border border-slate-200 rounded-md p-1">
                        <Button variant="ghost" size="icon" onClick={() => handlePriceChange(-1)} className="w-8 h-8 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded transition-colors">-</Button>
                        <input
                            type="text"
                            className="w-full bg-transparent text-right text-sm font-bold text-slate-700 outline-none px-2"
                            value={orderPrice === 0 ? '' : orderPrice.toLocaleString()}
                            onChange={(e) => handleManualPriceChange(e.target.value)}
                            placeholder="0"
                        />
                        <Button variant="ghost" size="icon" onClick={() => handlePriceChange(1)} className="w-8 h-8 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded transition-colors">+</Button>
                    </div>
                </div>

                <div className="flex items-center justify-between mt-1">
                    <span className="text-xs font-medium text-slate-500 w-12">수량</span>
                    <div className="flex-1">
                        <div className="flex justify-end mb-1">
                            <span className="text-[10px] text-slate-400">가능 {maxQty.toLocaleString()}주</span>
                        </div>
                        <div className="flex items-center bg-slate-50 border border-slate-200 rounded-md p-1">
                            <Button variant="ghost" size="icon" onClick={() => handleQuantityChange(-1)} className="w-8 h-8 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded transition-colors">-</Button>
                            <div className="flex flex-1 items-center justify-end px-2">
                                <input
                                    type="text"
                                    className="w-full bg-transparent text-right text-sm font-semibold outline-none"
                                    value={quantity === 0 ? '' : quantity.toLocaleString()}
                                    onChange={(e) => handleManualQuantityChange(e.target.value)}
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

            {quantity > 0 && (
                <div className="mt-4 mb-2 flex justify-between items-center text-sm font-bold animate-in fade-in zoom-in duration-200">
                    <span className="text-slate-500">주문 금액</span>
                    <span className={isBuy ? 'text-[#ce242b]' : 'text-[#0e48c4]'}>{totalAmount.toLocaleString()}원</span>
                </div>
            )}

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

            <ConfirmOrderModal
                isOpen={isConfirmModalOpen}
                onOpenChange={setIsConfirmModalOpen}
                stockName={stockName}
                isBuy={isBuy}
                orderPrice={orderPrice}
                quantity={quantity}
                totalAmount={totalAmount}
                fee={fee}
                tax={tax}
                feeRate={feeRate}
                taxRate={taxRate}
                totalWithFeeAndTax={totalWithFeeAndTax}
                onConfirm={handleConfirmTrade}
            />
        </div>
    );
}
