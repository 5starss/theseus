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

import type { TimeframeType } from '../../pages/StockDashboard';

export const StockChart = memo(function StockChart({ timeframe }: { timeframe: TimeframeType }) {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

    useEffect(() => {
        if (!chartContainerRef.current) return;

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

        // 1. 차트 인스턴스 생성 (디자인 시스템 적용)
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
                secondsVisible: true,
            },
        });

        // 2. 캔들스틱 시리즈 추가 (디자인 시스템 - Red: 상승, Blue: 하락)
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: "#fb2c36",     // Red / 상승
            downColor: "#2b7fff",   // Blue / 하락
            borderVisible: false,
            wickUpColor: "#fb2c36",
            wickDownColor: "#2b7fff",
        });

        // 3. 현재 시간 기준으로 60개의 과거 더미 데이터 생성
        const generateInitialData = () => {
            const data: CandlestickData<Time>[] = [];
            const now = Math.floor(Date.now() / 1000); // 현재 시간을 초 단위 변환

            // 현재 시간을 속한 캔들 주기의 시작점(00분 등)으로 내림하여 정렬
            const alignedNow = Math.floor(now / candlePeriod) * candlePeriod;

            const actualCurrentPrice = useStockStore.getState().currentPrice;
            let price = actualCurrentPrice - 6000; // 과거 가격 임의 시작점

            for (let i = 60; i >= 0; i--) {
                const time = (alignedNow - i * candlePeriod) as Time;

                if (i === 0) {
                    price = actualCurrentPrice;
                } else {
                    price = price + (Math.random() - 0.5) * 500;
                    price = Math.round(price / 100) * 100;
                }

                data.push({
                    time,
                    open: price,
                    high: price + 200,
                    low: price - 200,
                    close: i === 0 ? actualCurrentPrice : price + (Math.random() > 0.5 ? 100 : -100),
                });
            }
            return data;
        };

        const initialData = generateInitialData();
        candlestickSeries.setData(initialData);

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

        // 4. 시간이 흐르며 봉이 추가되는 라이브 업데이트 로직 (frontend 참고)
        let lastCandle = { ...initialData[initialData.length - 1] };

        const intervalId = setInterval(() => {
            const currentTime = Math.floor(Date.now() / 1000);

            const currentBucketTime = (Math.floor(currentTime / candlePeriod) * candlePeriod) as Time;

            // 🌟 전역 스토어에서 현재가 동기화 (호가창과 일치)
            const currentPrice = useStockStore.getState().currentPrice;

            // 이전 캔들과 시간이 다르다면 -> "새로운 봉 생성"
            if (currentBucketTime > lastCandle.time) {
                lastCandle = {
                    time: currentBucketTime,
                    open: lastCandle.close,
                    high: Math.max(lastCandle.close, currentPrice),
                    low: Math.min(lastCandle.close, currentPrice),
                    close: currentPrice,
                };
            }
            // 이전 캔들과 시간이 같다면 -> "현재 봉 위아래로 움직이기"
            else {
                lastCandle.high = Math.max(lastCandle.high, currentPrice);
                lastCandle.low = Math.min(lastCandle.low, currentPrice);
                lastCandle.close = currentPrice;
            }

            candlestickSeries.update(lastCandle);
        }, 200); // 0.2초마다 틱 데이터 주입

        // 차트 정리(Cleanup)
        return () => {
            clearInterval(intervalId);
            resizeObserver.disconnect();
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
        };
    }, [timeframe]);

    return (
        <div className="w-full h-full relative" ref={chartContainerRef}>
            {/* 툴팁이나 워터마크 등을 올리려면 이 내부에 추가 가능 */}
        </div>
    );
});
