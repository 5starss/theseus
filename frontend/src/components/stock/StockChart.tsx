import { useEffect, useRef, memo } from "react";
import {
    createChart,
    ColorType,
    CandlestickSeries,
    type IChartApi,
    type ISeriesApi,
    type CandlestickData,
    type Time,
} from "lightweight-charts";
import { useStockStore } from "../../store/useStockStore";
import { stockApi } from "../../api/stock";

import type { TimeframeType } from '../../pages/StockDashboard';

export const StockChart = memo(function StockChart({ timeframe }: { timeframe: TimeframeType }) {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const stockCode = useStockStore(state => state.stockCode);
    const lastCandleRef = useRef<CandlestickData<Time> | null>(null);

    // 1. 차트 초기화 및 백엔드 과거 캔들 데이터 주입
    useEffect(() => {
        if (!chartContainerRef.current) return;

        // 차트 인스턴스 생성 (디자인 시스템 적용)
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: "transparent" }, // 부모 bg-white 상속
                textColor: "#6a7282", // Light Text
            },
            grid: {
                vertLines: { color: "#f3f4f6" }, // Border Light
                horzLines: { color: "#f3f4f6" },
            },
            crosshair: {
                mode: 1, // Normal mode
                vertLine: { width: 1, color: "#99a1af", style: 3 },
                horzLine: { width: 1, color: "#99a1af", style: 3 },
            },
            rightPriceScale: {
                borderColor: "#f3f4f6", // Border Light
            },
            timeScale: {
                borderColor: "#f3f4f6",
                timeVisible: true,
                secondsVisible: false,
            },
        });

        // 캔들스틱 시리즈 추가 (디자인 시스템 - Red: 상승, Blue: 하락)
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: "#fb2c36",     // Red / 상승
            downColor: "#2b7fff",   // Blue / 하락
            borderVisible: false,
            wickUpColor: "#fb2c36",
            wickDownColor: "#2b7fff",
        });

        chartRef.current = chart;
        seriesRef.current = candlestickSeries;

        // Resize 관찰자 설정 
        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };
        const resizeObserver = new ResizeObserver(handleResize);
        resizeObserver.observe(chartContainerRef.current);

        let isMounted = true;

        // 백엔드 명세 기반 캔들 데이터 로딩
        const fetchInitialData = async () => {
            let tfStr = 'D';
            switch (timeframe) {
                case '1m': tfStr = 'm'; break;
                case '1h': tfStr = 'h'; break;
                case '1d': tfStr = 'D'; break;
                case '1w': tfStr = 'W'; break;
            }

            const history = await stockApi.getCandles(stockCode, tfStr, 50);
            if (!isMounted) return;

            const chartData: CandlestickData<Time>[] = history.map(d => ({
                time: (new Date(d.timestamp).getTime() / 1000) as Time,
                open: d.open,
                high: d.high,
                low: d.low,
                close: d.close,
            }));

            // TradingView 데이터 구조 특성상 오름차순 보장이 필요
            chartData.sort((a, b) => (a.time as number) - (b.time as number));

            candlestickSeries.setData(chartData);

            if (chartData.length > 0) {
                lastCandleRef.current = { ...chartData[chartData.length - 1] };
            }

            // 화면 우측으로 피팅
            chart.timeScale().fitContent();
        };

        fetchInitialData();

        return () => {
            isMounted = false;
            resizeObserver.disconnect();
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
        };
    }, [stockCode, timeframe]);

    // 2. 시간이 흐르면서 변동하는 라이브 틱 갱신 (Zustand subscribe)
    useEffect(() => {
        const unsubscribe = useStockStore.subscribe(
            (state, prevState) => {
                const currentPrice = state.currentPrice;
                if (currentPrice === prevState.currentPrice) return;

                const getCandlePeriod = (tf: TimeframeType) => {
                    switch (tf) {
                        case '1m': return 60;
                        case '1h': return 3600;
                        case '1d': return 86400;
                        case '1w': return 604800; // 7 days
                        default: return 60;
                    }
                };
                const candlePeriod = getCandlePeriod(timeframe);
                const currentTime = Math.floor(Date.now() / 1000);
                const currentBucketTimeNum = Math.floor(currentTime / candlePeriod) * candlePeriod;
                const currentBucketTime = currentBucketTimeNum as Time;

                let lastCandle = lastCandleRef.current;
                if (!lastCandle || !seriesRef.current) return;

                const lastTimeSec = lastCandle.time as number;

                if (currentBucketTimeNum > lastTimeSec) {
                    // 새로운 봉 생성
                    lastCandle = {
                        time: currentBucketTime,
                        open: lastCandle.close,
                        high: Math.max(lastCandle.close, currentPrice),
                        low: Math.min(lastCandle.close, currentPrice),
                        close: currentPrice,
                    };
                } else {
                    // 기존 봉 갱신
                    lastCandle.high = Math.max(lastCandle.high, currentPrice);
                    lastCandle.low = Math.min(lastCandle.low, currentPrice);
                    lastCandle.close = currentPrice;
                }

                lastCandleRef.current = lastCandle;
                seriesRef.current.update(lastCandle);
            }
        );

        return () => unsubscribe();
    }, [timeframe]);


    return (
        <div className="w-full h-full relative" ref={chartContainerRef}>
            {/* 툴팁이나 워터마크 등을 올리려면 이 내부에 추가 가능 */}
        </div>
    );
});
