import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { StockHeader } from "../components/stock/StockHeader";
import { Orderbook } from "../components/stock/Orderbook";
import { OrderPanel, MyStockInfo, MyOrderHistory } from "../components/stock/trade";
import { StockChart } from "../components/stock/StockChart";
import { CommunityTab } from "../components/stock/community/CommunityTab";
import { useStockStore } from "../store/useStockStore";
import { useAccountStore } from "../store/useAccountStore";
import { useAuthStore } from "../store/useAuthStore";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";

export type TimeframeType = "1m" | "1h" | "1d" | "1w";

export default function StockDashboard() {
  const { code } = useParams<{ code: string }>();
  const connectStockStream = useStockStore((state) => state.connectStockStream);
  const disconnectStockStream = useStockStore((state) => state.disconnectStockStream);
  const stockName = useStockStore((state) => state.stockName);
  const {
    fetchBalance,
    fetchPositions,
    fetchPendingOrders,
    fetchCompletedOrders,
  } = useAccountStore();
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
  const [timeframe, setTimeframeState] = useState<TimeframeType>(() => {
    const saved = localStorage.getItem("stock_chart_timeframe");
    return (saved as TimeframeType) || "1m";
  });

  const setTimeframe = (tf: TimeframeType) => {
    setTimeframeState(tf);
    localStorage.setItem("stock_chart_timeframe", tf);
  };

  useEffect(() => {
    if (code) {
      connectStockStream(code);
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
  }, [
    code,
    connectStockStream,
    disconnectStockStream,
    isLoggedIn,
    fetchBalance,
    fetchPositions,
    fetchPendingOrders,
    fetchCompletedOrders,
  ]);

  return (
    <div className="flex h-full w-full flex-col gap-4 overflow-hidden bg-slate-50 p-4">
      <Tabs defaultValue="trade" className="flex-1 min-h-0">
        <TabsList
          variant="line"
          className="rounded-xl border border-slate-200 bg-white p-1"
        >
          <TabsTrigger value="trade" className="px-4">
            거래
          </TabsTrigger>
          <TabsTrigger value="community" className="px-4">
            커뮤니티
          </TabsTrigger>
        </TabsList>

        <TabsContent value="trade" className="mt-4 flex-1 min-h-0">
          <div className="flex min-h-0 min-w-[1100px] flex-1 flex-col gap-4">
            <StockHeader />

            <div className="flex flex-1 gap-4 min-h-0">
              <div className="flex min-w-[400px] flex-1 flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-4 flex items-center gap-2 shrink-0">
                  <Button
                    onClick={() => setTimeframe("1m")}
                    variant={timeframe === "1m" ? "default" : "ghost"}
                    className={`h-7 rounded-md px-3 text-xs font-medium shadow-none transition-colors ${
                      timeframe === "1m"
                        ? "bg-blue-50 font-bold text-blue-600 hover:bg-blue-100 hover:text-blue-700"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    1분
                  </Button>
                  <div className="mx-1 h-4 w-px bg-slate-300" />
                  <Button
                    onClick={() => setTimeframe("1d")}
                    variant={timeframe === "1d" ? "default" : "ghost"}
                    className={`h-7 rounded-md px-3 text-xs font-medium shadow-none transition-colors ${
                      timeframe === "1d"
                        ? "bg-blue-50 font-bold text-blue-600 hover:bg-blue-100 hover:text-blue-700"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    일
                  </Button>
                </div>

                <div className="flex min-h-[400px] flex-1 flex-col bg-white">
                  <StockChart timeframe={timeframe} />
                </div>
              </div>

              <div className="flex h-full w-[320px] flex-none flex-col gap-4">
                <div className="h-[178px] shrink-0">
                  <Orderbook />
                </div>
                <div className="flex-1">
                  <OrderPanel />
                </div>
              </div>

              <div className="flex h-full w-[320px] flex-none flex-col gap-4">
                <div className="h-[320px] shrink-0">
                  <MyOrderHistory />
                </div>
                <div className="flex-1">
                  <MyStockInfo />
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="community" className="mt-4">
          <CommunityTab stockCode={code ?? ""} stockName={stockName} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
