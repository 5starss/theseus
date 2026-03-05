import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { StockHeader } from "../components/stock/StockHeader";
import { Orderbook } from "../components/stock/Orderbook";
import { OrderPanel, MyStockInfo, MyOrderHistory } from "../components/stock/TradePanels";
import { StockChart } from "../components/stock/StockChart";
import { useStockStore } from "../store/useStockStore";
import { useState } from "react";
import { Button } from "@/components/ui/button";


export type TimeframeType = '1m' | '1h' | '1d' | '1w';

export default function StockDashboard() {
    const { code } = useParams<{ code: string }>();
    const connectStockStream = useStockStore(state => state.connectStockStream);
    const disconnectStockStream = useStockStore(state => state.disconnectStockStream);
    const [timeframe, setTimeframe] = useState<TimeframeType>('1m');

    useEffect(() => {
        if (code) {
            connectStockStream(code);
        }

        return () => {
            disconnectStockStream();
        };
    }, [code, connectStockStream, disconnectStockStream]);

    return (
        <div className="w-full h-full flex flex-col p-4 gap-4 overflow-hidden bg-slate-50">

            {/* Top Info Bar */}
            <StockHeader />

            {/* Main Trading Area */}
            <div className="flex-1 flex flex-col lg:flex-row gap-4 min-h-0">

                {/* Left Col: Chart & Tools */}
                <div className="flex-1 flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 p-4 min-w-[500px]">
                    <div className="flex items-center gap-2 mb-4 shrink-0">
                        <Button
                            onClick={() => setTimeframe('1m')}
                            variant={timeframe === '1m' ? 'default' : 'ghost'}
                            className={`h-7 px-3 font-medium text-xs rounded-md transition-colors shadow-none ${timeframe === '1m' ? 'bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 font-bold' : 'text-slate-600 hover:bg-slate-100'}`}>
                            1분
                        </Button>
                        <Button
                            onClick={() => setTimeframe('1h')}
                            variant={timeframe === '1h' ? 'default' : 'ghost'}
                            className={`h-7 px-3 font-medium text-xs rounded-md transition-colors shadow-none ${timeframe === '1h' ? 'bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 font-bold' : 'text-slate-600 hover:bg-slate-100'}`}>
                            1시간
                        </Button>
                        <div className="w-px h-4 bg-slate-300 mx-1"></div>
                        <Button
                            onClick={() => setTimeframe('1d')}
                            variant={timeframe === '1d' ? 'default' : 'ghost'}
                            className={`h-7 px-3 font-medium text-xs rounded-md transition-colors shadow-none ${timeframe === '1d' ? 'bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 font-bold' : 'text-slate-600 hover:bg-slate-100'}`}>
                            일
                        </Button>
                        <Button
                            onClick={() => setTimeframe('1w')}
                            variant={timeframe === '1w' ? 'default' : 'ghost'}
                            className={`h-7 px-3 font-medium text-xs rounded-md transition-colors shadow-none ${timeframe === '1w' ? 'bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 font-bold' : 'text-slate-600 hover:bg-slate-100'}`}>
                            주
                        </Button>
                    </div>

                    <div className="flex-1 bg-white flex flex-col min-h-[400px]">
                        <StockChart timeframe={timeframe} />
                    </div>
                </div>

                {/* Middle Col: Orderbook & Trading */}
                <div className="flex-[3] min-w-[320px] max-w-[350px] flex flex-col gap-4 h-full hidden lg:flex">
                    <div className="shrink-0 h-[178px]">
                        <Orderbook />
                    </div>
                    <div className="flex-1">
                        <OrderPanel />
                    </div>
                </div>

                {/* Right Col: Order History & My Info */}
                <div className="flex-[3] min-w-[320px] max-w-[350px] flex flex-col gap-4 h-full hidden lg:flex">
                    <div className="shrink-0 h-[320px]">
                        <MyOrderHistory />
                    </div>
                    <div className="flex-1">
                        <MyStockInfo />
                    </div>
                </div>
            </div>
        </div>
    );
}
