import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { StockHeader } from "../components/stock/StockHeader";
import { Orderbook } from "../components/stock/Orderbook";
import { OrderPanel, MyStockInfo, MyOrderHistory } from "../components/stock/TradePanels";
import { StockChart } from "../components/stock/StockChart";
import { useStockStore } from "../store/useStockStore";
import { useAccountStore } from "../store/useAccountStore";
import { useAuthStore } from "../store/useAuthStore";
import { useState } from "react";
import { Button } from "@/components/ui/button";


export type TimeframeType = '1m' | '1h' | '1d' | '1w';

export default function StockDashboard() {
    const { code } = useParams<{ code: string }>();
    const connectStockStream = useStockStore(state => state.connectStockStream);
    const disconnectStockStream = useStockStore(state => state.disconnectStockStream);
    const { fetchBalance, fetchPositions, fetchPendingOrders, fetchCompletedOrders } = useAccountStore();
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const [timeframe, setTimeframeState] = useState<TimeframeType>(() => {
        const saved = localStorage.getItem('stock_chart_timeframe');
        return (saved as TimeframeType) || '1m';
    });

    const setTimeframe = (tf: TimeframeType) => {
        setTimeframeState(tf);
        localStorage.setItem('stock_chart_timeframe', tf);
    };

    useEffect(() => {
        if (code) {
            connectStockStream(code);
            // 상세 페이지 진입 시 계좌 데이터 최신화 (로그인 된 경우)
            if (isLoggedIn) {
                fetchBalance();
                fetchPositions();
                fetchPendingOrders();
                fetchCompletedOrders({ ticker: code, size: 20 });
            }
        }

        return () => {
            disconnectStockStream();
        };
    }, [code, connectStockStream, disconnectStockStream, isLoggedIn, fetchBalance, fetchPositions, fetchPendingOrders, fetchCompletedOrders]);

    return (
        <div className="w-full h-full flex flex-col p-4 gap-4 bg-slate-50 overflow-hidden">
            {/* Main Trading Area */}
            <div className="flex-1 flex flex-col gap-4 min-h-0 min-w-[1100px]">
                {/* Top Info Bar */}
                <StockHeader />

                <div className="flex-1 flex gap-4 min-h-0">

                    {/* Left Col: Chart & Tools */}
                    <div className="flex-1 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 p-4 min-w-[400px]">
                        <div className="flex items-center gap-2 mb-4 shrink-0">
                            <Button
                                onClick={() => setTimeframe('1m')}
                                variant={timeframe === '1m' ? 'default' : 'ghost'}
                                className={`h-7 px-3 font-medium text-xs rounded-md transition-colors shadow-none ${timeframe === '1m' ? 'bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 font-bold' : 'text-slate-600 hover:bg-slate-100'}`}>
                                1분
                            </Button>
                            <div className="w-px h-4 bg-slate-300 mx-1"></div>
                            <Button
                                onClick={() => setTimeframe('1d')}
                                variant={timeframe === '1d' ? 'default' : 'ghost'}
                                className={`h-7 px-3 font-medium text-xs rounded-md transition-colors shadow-none ${timeframe === '1d' ? 'bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 font-bold' : 'text-slate-600 hover:bg-slate-100'}`}>
                                일
                            </Button>
                        </div>

                        <div className="flex-1 bg-white flex flex-col min-h-[400px]">
                            <StockChart timeframe={timeframe} />
                        </div>
                    </div>

                    {/* Middle Col: Orderbook & Trading */}
                    <div className="flex flex-none w-[320px] flex-col gap-4 h-full">
                        <div className="shrink-0 h-[178px]">
                            <Orderbook />
                        </div>
                        <div className="flex-1">
                            <OrderPanel />
                        </div>
                    </div>

                    {/* Right Col: Order History & My Info */}
                    <div className="flex flex-none w-[320px] flex-col gap-4 h-full">
                        <div className="shrink-0 h-[320px]">
                            <MyOrderHistory />
                        </div>
                        <div className="flex-1">
                            <MyStockInfo />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
