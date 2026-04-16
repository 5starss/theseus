import { useState, useEffect, useCallback, useMemo } from "react";
import { useStockStore } from "../../../store/useStockStore";
import { useAccountStore } from "../../../store/useAccountStore";
import { useConfigStore } from "../../../store/useConfigStore";
import { getTickSize } from "../../../utils/priceUtils";

export function useOrderForm(orderType: "buy" | "sell") {
    const isBuy = orderType === "buy";
    
    // Store states
    const currentPrice = useStockStore(state => state.currentPrice);
    const stockCode = useStockStore(state => state.stockCode);
    const selectedOrderPrice = useStockStore(state => state.selectedOrderPrice);
    const feeRate = useConfigStore(state => state.feeRate);
    const taxRate = useConfigStore(state => state.taxRate);
    const cashBalance = useAccountStore(state => state.cashBalance);
    const portfolio = useAccountStore(state => state.portfolio);

    // Form states
    const [orderPrice, setOrderPrice] = useState(0);
    const [quantity, setQuantity] = useState(0);

    // 종목 변경 시 초기화
    useEffect(() => {
        setOrderPrice(currentPrice);
        setQuantity(0);
    }, [stockCode]);

    // 현재가 로드 시
    useEffect(() => {
        if (orderPrice === 0 && currentPrice > 0) {
            setOrderPrice(currentPrice);
        }
    }, [currentPrice]);

    // 호가 클릭 시
    useEffect(() => {
        if (selectedOrderPrice > 0) {
            setOrderPrice(selectedOrderPrice);
        }
    }, [selectedOrderPrice]);

    // 수치 계산 (Memoized)
    const selectedStock = useMemo(() => portfolio.find(p => p.code === stockCode), [portfolio, stockCode]);
    const availableSharesCount = selectedStock?.availableShares || 0;

    const maxBuyQty = useMemo(() => {
        if (orderPrice <= 0) return 0;
        let n = Math.floor(cashBalance / orderPrice);
        while (n > 0 && n * orderPrice + Math.floor(n * orderPrice * feeRate) > cashBalance) n--;
        return n;
    }, [orderPrice, cashBalance, feeRate]);

    const maxQty = isBuy ? maxBuyQty : availableSharesCount;

    const totalAmount = orderPrice * quantity;
    const fee = Math.floor(totalAmount * feeRate);
    const tax = isBuy ? 0 : Math.floor(totalAmount * taxRate);
    const totalWithFeeAndTax = isBuy ? totalAmount + fee : totalAmount - fee - tax;

    // Handlers
    const handlePriceChange = useCallback((delta: number) => {
        setOrderPrice(prev => {
            const tick = getTickSize(prev);
            const next = prev + (delta * tick);
            return Math.max(0, next);
        });
    }, []);

    const handleManualPriceChange = (val: string) => {
        const num = parseInt(val.replace(/[^0-9]/g, ''), 10);
        setOrderPrice(isNaN(num) ? 0 : num);
    };

    const handleQuantityChange = useCallback((delta: number) => {
        setQuantity(prev => {
            const next = prev + delta;
            if (next < 0) return 0;
            if (next > maxQty) return maxQty;
            return next;
        });
    }, [maxQty]);

    const handleManualQuantityChange = (val: string) => {
        const num = parseInt(val.replace(/[^0-9]/g, ''), 10);
        let next = isNaN(num) ? 0 : num;
        if (next > maxQty) next = maxQty;
        setQuantity(next);
    };

    const handlePercentage = (percent: number) => {
        setQuantity(Math.floor(maxQty * percent));
    };

    return {
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
    };
}
