import { useEffect, useRef, memo } from "react";
import {
    createChart,
    ColorType,
    LineStyle,
    CrosshairMode,
    CandlestickSeries,
    HistogramSeries,
    LineSeries,
    type IChartApi,
    type ISeriesApi,
    type CandlestickData,
    type LineData,
    type HistogramData,
    type Time,
} from "lightweight-charts";
import { useStockStore } from "../../store/useStockStore";
import { stockApi } from "../../api/stock";

import type { TimeframeType } from '../../pages/StockDashboard';

interface ExtendedCandle extends CandlestickData<Time> {
    volume?: number;
}

// 로컬 시간 기준 YYYY-MM-DDTHH:mm:ss 포맷 생성
const toLocalISOString = (date: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};

// 캔들 데이터 정제 유틸리티
const processCandleData = (history: any[]): { candles: ExtendedCandle[], volumes: HistogramData<Time>[] } => {
    if (!history || !Array.isArray(history)) return { candles: [], volumes: [] };

    const cleaned = history
        .filter(d => d && d.timestamp && isFinite(Number(d.open)) && isFinite(Number(d.high)) && isFinite(Number(d.low)) && isFinite(Number(d.close)))
        .map(d => ({
            time: (new Date(d.timestamp).getTime() / 1000) as Time,
            open: Number(d.open),
            high: Number(d.high),
            low: Number(d.low),
            close: Number(d.close),
            volume: Number(d.volume || 0),
        }))
        .sort((a, b) => (a.time as number) - (b.time as number));

    const uniqueCandles: ExtendedCandle[] = [];
    const uniqueVolumes: HistogramData<Time>[] = [];

    for (const item of cleaned) {
        const volumeColor = item.close >= item.open ? "#fb2c36" : "#2b7fff";
        if (uniqueCandles.length === 0 || (item.time as number) > (uniqueCandles[uniqueCandles.length - 1].time as number)) {
            uniqueCandles.push({ ...item });
            uniqueVolumes.push({ time: item.time, value: item.volume, color: volumeColor });
        } else if ((item.time as number) === (uniqueCandles[uniqueCandles.length - 1].time as number)) {
            uniqueCandles[uniqueCandles.length - 1] = { ...item };
            uniqueVolumes[uniqueVolumes.length - 1] = { time: item.time, value: item.volume, color: volumeColor };
        }
    }
    return { candles: uniqueCandles, volumes: uniqueVolumes };
};

// 이동평균선(MA) 계산
const calculateMA = (data: ExtendedCandle[], period: number): LineData<Time>[] => {
    const res: LineData<Time>[] = [];
    if (data.length < period) return res;
    for (let i = period - 1; i < data.length; i++) {
        let sum = 0;
        let valid = true;
        for (let j = 0; j < period; j++) {
            const val = data[i - j].close;
            if (!isFinite(val)) { valid = false; break; }
            sum += val;
        }
        if (valid) res.push({ time: data[i].time, value: sum / period });
    }
    return res;
};

export const StockChart = memo(function StockChart({ timeframe }: { timeframe: TimeframeType }) {
    const priceContainerRef = useRef<HTMLDivElement>(null);
    const volumeContainerRef = useRef<HTMLDivElement>(null);

    const priceChartRef = useRef<IChartApi | null>(null);
    const volumeChartRef = useRef<IChartApi | null>(null);

    const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
    const maSeriesRefs = useRef<Record<string, ISeriesApi<"Line">>>({});

    const stockCode = useStockStore(state => state.stockCode);
    const candles = useStockStore(state => state.candles);
    const setCandles = useStockStore(state => state.setCandles);
    const appendHistoricalCandles = useStockStore(state => state.appendHistoricalCandles);

    const lastCandleRef = useRef<ExtendedCandle | null>(null);
    const isLoadingMore = useRef(false);
    const hasHitLimit = useRef(false);
    const candlesRef = useRef(candles);

    useEffect(() => { candlesRef.current = candles; }, [candles]);

    //     // 초기화 가드
    useEffect(() => {
        setCandles([]);
        hasHitLimit.current = false;
        isLoadingMore.current = false;
        lastCandleRef.current = null;
    }, [stockCode, timeframe, setCandles]);

    // 1. 차트 엔진 초기화 및 동기화
    useEffect(() => {
        if (!priceContainerRef.current || !volumeContainerRef.current) return;

        const isIntraday = timeframe === '1m' || timeframe === '1h';

        // 공통 옵션
        const sharedOptions = {
            layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#6a7282" },
            grid: { vertLines: { color: "#f3f4f6" }, horzLines: { color: "#f3f4f6" } },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: { width: 1 as const, color: "#99a1af", style: LineStyle.LargeDashed },
                horzLine: { width: 1 as const, color: "#99a1af", style: LineStyle.LargeDashed }
            },
            localization: {
                locale: 'ko-KR',
                priceFormatter: (price: number) => Math.round(price).toLocaleString('ko-KR'),
                timeFormatter: (time: number) => {
                    const date = new Date(time * 1000);
                    const formatOptions: Intl.DateTimeFormatOptions = {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                    };
                    if (isIntraday) {
                        formatOptions.hour = '2-digit';
                        formatOptions.minute = '2-digit';
                        formatOptions.hour12 = false;
                    }
                    return date.toLocaleString('ko-KR', formatOptions);
                },
            },
        };

        // 메인 차트 (가격)
        const priceChart = createChart(priceContainerRef.current, {
            ...sharedOptions,
            layout: {
                ...sharedOptions.layout,
                attributionLogo: false,
            },
            rightPriceScale: { borderColor: "#f3f4f6", autoScale: true, visible: true, minimumWidth: 80 },
            timeScale: {
                borderColor: "#f3f4f6",
                visible: false, // 상단 차트의 시간축은 숨김 (하단 차트와 공유)
                shiftVisibleRangeOnNewBar: true,
                barSpacing: isIntraday ? 10 : 6,
            },
        });

        // 서브 차트 (거래량)
        const volumeChart = createChart(volumeContainerRef.current, {
            ...sharedOptions,
            localization: {
                ...sharedOptions.localization,
                priceFormatter: (val: number) => {
                    if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                    if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
                    return Math.round(val).toLocaleString();
                },
            },
            rightPriceScale: { borderColor: "#f3f4f6", autoScale: true, visible: true, minimumWidth: 80 },
            timeScale: {
                borderColor: "#f3f4f6",
                visible: true,
                shiftVisibleRangeOnNewBar: true,
                barSpacing: isIntraday ? 10 : 6,
                tickMarkFormatter: (time: number, tickMarkType: number) => {
                    const date = new Date(time * 1000);
                    if (isIntraday) {
                        return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
                    }
                    if (tickMarkType === 0) return `${date.getFullYear()}`;
                    if (tickMarkType === 1) return `${date.getMonth() + 1}월`;
                    return `${date.getDate()}일`;
                },
            },
        });

        const candlestickSeries = priceChart.addSeries(CandlestickSeries, {
            upColor: "#fb2c36", downColor: "#2b7fff", borderVisible: false, wickUpColor: "#fb2c36", wickDownColor: "#2b7fff",
        });

        const volumeSeries = volumeChart.addSeries(HistogramSeries, {
            color: '#2b7fff', priceFormat: { type: 'volume' },
        });

        // 이동평균선
        ["ma5", "ma20", "ma60"].forEach((id, idx) => {
            const colors = ["#10b981", "#f59e0b", "#8b5cf6"];
            maSeriesRefs.current[id] = priceChart.addSeries(LineSeries, { color: colors[idx], lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        });

        // ──────────────── 동기화 ────────────────
        // 1. 타임스케일
        priceChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
            if (range) volumeChart.timeScale().setVisibleLogicalRange(range);
        });
        volumeChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
            if (range) priceChart.timeScale().setVisibleLogicalRange(range);
        });

        // 2-1. 크로스헤어 동기화(가격차트 -> 거래량차트)
        priceChart.subscribeCrosshairMove((param) => {
            if (param.time) volumeChart.setCrosshairPosition(0, param.time, volumeSeries);
            else volumeChart.clearCrosshairPosition();
        });
        // 2-2. 크로스헤어 동기화(거래량차트 -> 가격차트)
        volumeChart.subscribeCrosshairMove((param) => {
            if (param.time) priceChart.setCrosshairPosition(0, param.time, candlestickSeries);
            else priceChart.clearCrosshairPosition();
        });

        // 3. 레이블 노출 제어 (DOM 이벤트를 통한 안정화)
        const onPriceEnter = () => {
            volumeChart.applyOptions({ crosshair: { horzLine: { labelVisible: false } } });
        };
        const onVolumeEnter = () => {
            volumeChart.applyOptions({ crosshair: { horzLine: { labelVisible: true } } });
        };

        const priceEl = priceContainerRef.current;
        const volumeEl = volumeContainerRef.current;
        if (priceEl) priceEl.addEventListener('mouseenter', onPriceEnter);
        if (volumeEl) volumeEl.addEventListener('mouseenter', onVolumeEnter);

        // ──────────────── 참조 ────────────────
        priceChartRef.current = priceChart;
        volumeChartRef.current = volumeChart;
        candlestickSeriesRef.current = candlestickSeries;
        volumeSeriesRef.current = volumeSeries;

        // ──────────────── 페이징 ────────────────
        // 1. 페이징 로직(가격차트)
        priceChart.timeScale().subscribeVisibleTimeRangeChange(async () => {
            // 1-1. 로딩 중이거나 최�?치에 ?�달?�으�?리턴
            if (hasHitLimit.current || isLoadingMore.current) return;

            // 1-2. 현재 시각 범위 가져오기
            const timeScale = priceChart.timeScale();
            const visibleRange = timeScale.getVisibleRange();
            if (!visibleRange || !candlesRef.current.length) return;

            // 1-3. 로직 실행
            const logicalRange = timeScale.getVisibleLogicalRange();
            if (logicalRange && logicalRange.from < 100) {
                isLoadingMore.current = true;
                const firstTime = candlesRef.current[0].time as number;
                const oldestDate = new Date(firstTime * 1000);

                if (oldestDate <= new Date('2024-03-14T00:00:00Z')) {
                    hasHitLimit.current = true;
                    isLoadingMore.current = false;
                    return;
                }

                // 1-4. API 호출
                const tfStr = timeframe === '1m' ? '1m' : (timeframe === '1h' ? '1h' : (timeframe === '1d' ? '1d' : '1w'));
                try {
                    const history = await stockApi.getCandles(stockCode, tfStr, 300, toLocalISOString(oldestDate));

                    // 1-5. 데이터 처리
                    if (history && history.length > 0) {
                        const { candles: moreCandles } = processCandleData(history);
                        const filtered = moreCandles.filter(d => (d.time as number) < firstTime);
                        if (filtered.length > 0) appendHistoricalCandles(filtered);
                        else hasHitLimit.current = true;
                    } else hasHitLimit.current = true;
                } catch (e) { console.error("Paging error", e); }
                finally { setTimeout(() => { isLoadingMore.current = false; }, 200); }
            }
        });

        // 2. 리사이즈 핸들러
        const handleResize = () => {
            if (priceContainerRef.current) priceChart.applyOptions({ width: priceContainerRef.current.clientWidth });
            if (volumeContainerRef.current) volumeChart.applyOptions({ width: volumeContainerRef.current.clientWidth });
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (priceEl) priceEl.removeEventListener('mouseenter', onPriceEnter);
            if (volumeEl) volumeEl.removeEventListener('mouseenter', onVolumeEnter);
            priceChart.remove();
            volumeChart.remove();
            priceChartRef.current = null;
            volumeChartRef.current = null;
            candlestickSeriesRef.current = null;
            volumeSeriesRef.current = null;
            maSeriesRefs.current = {};
        };
    }, [stockCode, timeframe]);

    // 2. 초기 로딩
    useEffect(() => {
        let isMounted = true;
        (async () => {
            const isIntraday = timeframe === '1m' || timeframe === '1h';
            const tfStr = timeframe === '1m' ? '1m' : (timeframe === '1h' ? '1h' : (timeframe === '1d' ? '1d' : '1w'));
            const initialLimit = isIntraday ? 1000 : 100;
            const history = stockCode ? await stockApi.getCandles(stockCode, tfStr, initialLimit) : [];
            if (!isMounted) return;

            const { candles: initialCandles } = processCandleData(history);
            setCandles(initialCandles);

            if (initialCandles.length > 0) {
                lastCandleRef.current = { ...initialCandles[initialCandles.length - 1] };
                if (priceChartRef.current) {
                    const timeScale = priceChartRef.current.timeScale();
                    if (isIntraday) timeScale.setVisibleLogicalRange({ from: Math.max(0, initialCandles.length - 100), to: initialCandles.length });
                    else timeScale.fitContent();
                }
            }
        })();
        return () => { isMounted = false; };
    }, [stockCode, timeframe]);

    // 3. 데이터 업데이트 (동시 피딩)
    useEffect(() => {
        if (candlestickSeriesRef.current && volumeSeriesRef.current && candles.length > 0) {
            try {
                candlestickSeriesRef.current.setData(candles);

                const volumeData = candles.map((c: any, i: number) => {
                    const prevClose = i > 0 ? candles[i - 1].close : c.open;
                    return { time: c.time, value: c.volume || 0, color: c.close >= prevClose ? "#fb2c36" : "#2b7fff" };
                });
                volumeSeriesRef.current.setData(volumeData);

                [5, 20, 60].forEach(p => {
                    const data = calculateMA(candles, p);
                    if (maSeriesRefs.current[`ma${p}`]) maSeriesRefs.current[`ma${p}`].setData(data);
                });
                lastCandleRef.current = { ...candles[candles.length - 1] };
            } catch (e) { console.error("[Chart] setData error:", e); }
        }
    }, [candles]);

    // 4. 리얼타임 업데이트
    useEffect(() => {
        const sub = useStockStore.subscribe((state, prev) => {
            const price = state.currentPrice;
            if (price === prev.currentPrice || !isFinite(price) || !lastCandleRef.current || !candlestickSeriesRef.current) return;

            const candlePeriod = { '1m': 60, '1h': 3600, '1d': 86400, '1w': 604800 }[timeframe] || 60;
            const currentBucketTimeNum = Math.floor(Date.now() / 1000 / candlePeriod) * candlePeriod;
            const lastTimeSec = lastCandleRef.current.time as number;
            if (currentBucketTimeNum < lastTimeSec) return;

            let updated: ExtendedCandle;
            if (currentBucketTimeNum > lastTimeSec) {
                updated = { time: currentBucketTimeNum as Time, open: lastCandleRef.current.close, high: Math.max(lastCandleRef.current.close, price), low: Math.min(lastCandleRef.current.close, price), close: price, volume: 0 };
            } else {
                updated = { ...lastCandleRef.current, high: Math.max(lastCandleRef.current.high, price), low: Math.min(lastCandleRef.current.low, price), close: price };
            }

            lastCandleRef.current = updated;
            candlestickSeriesRef.current.update(updated);
            if (volumeSeriesRef.current) {
                const prevClose = updated.time === (lastTimeSec as any) ? (candlesRef.current.slice(-2)[0]?.close || updated.open) : lastCandleRef.current.close;
                volumeSeriesRef.current.update({ time: updated.time, value: updated.volume || 0, color: updated.close >= prevClose ? "#fb2c36" : "#2b7fff" });
            }

            const curCandles = [...candlesRef.current];
            if (curCandles.length > 0 && (curCandles[curCandles.length - 1].time as number) === currentBucketTimeNum) curCandles[curCandles.length - 1] = updated;
            else curCandles.push(updated);

            [5, 20, 60].forEach(p => {
                if (curCandles.length >= p) {
                    let sum = 0;
                    for (let j = 0; j < p; j++) sum += curCandles[curCandles.length - 1 - j].close;
                    if (maSeriesRefs.current[`ma${p}`]) maSeriesRefs.current[`ma${p}`].update({ time: updated.time, value: sum / p });
                }
            });
        });
        return () => sub();
    }, [timeframe]);

    return (
        <div className="w-full h-full flex flex-col bg-white">
            <div ref={priceContainerRef} className="flex-grow min-h-[50%]" />
            <div className="h-[1px] bg-gray-200 w-full" />
            <div ref={volumeContainerRef} className="h-32 min-h-[128px]" />
        </div>
    );
});

