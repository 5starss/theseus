import React from 'react';
import StockRow from './StockRow';

import { useMarketStore } from '../../store/useMarketStore';

const tabs = ['거래대금', '현재가', '등락률', '종목명', '거래량'];

const StockList: React.FC = () => {
    const [activeTab, setActiveTab] = React.useState('거래대금');

    // useMarketStore에서 stocksMap과 스트림 연결/해제 함수를 가져옴
    const stocksMap = useMarketStore(state => state.stocks);
    const connectMarketStream = useMarketStore(state => state.connectMarketStream);
    const disconnectMarketStream = useMarketStore(state => state.disconnectMarketStream);

    // 컴포넌트가 마운트될 때 스트림을 연결하고, 언마운트될 때 스트림을 정리하는 useEffect
    React.useEffect(() => {
        connectMarketStream();
        return () => disconnectMarketStream();
    }, [connectMarketStream, disconnectMarketStream]);

    // activeTab에 따라 stocksMap을 배열로 변환한 후 정렬하여 sortedStocks를 생성.
    const [currentTime, setCurrentTime] = React.useState('');

    React.useEffect(() => {
        const updateTime = () => {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            setCurrentTime(`오늘 ${hours}:${minutes} 기준`);
        };
        updateTime();
        // 1분마다 시간 갱신
        const interval = setInterval(updateTime, 60000);
        return () => clearInterval(interval);
    }, []);
    const sortedStocks = React.useMemo(() => {
        const stockArray = Object.values(stocksMap);

        return stockArray.sort((a, b) => {
            switch (activeTab) {
                case '현재가':
                    return b.currentPrice - a.currentPrice;
                case '등락률':
                    return b.changeRate - a.changeRate;
                case '종목명':
                    return a.name.localeCompare(b.name, 'ko-KR');
                case '거래량':
                    return b.accVolume - a.accVolume;
                case '거래대금':
                default:
                    return (b.currentPrice * b.accVolume) - (a.currentPrice * a.accVolume);
            }
        }).map((stock, index) => ({
            ...stock,
            rank: index + 1 // 정렬된 순서에 따라 rank 업데이트
        }));
    }, [stocksMap, activeTab]);

    return (
        <div className="flex-1 w-full flex flex-col items-center bg-[#f9fafb] p-[12px] min-h-0">
            <div className="w-full bg-white border border-[#f3f4f6] rounded-[12px] shadow-sm flex flex-col flex-1 min-h-0 overflow-hidden">

                {/* Tabs */}
                <div className="px-[12px] pt-[12px]">
                    <div className="bg-[#f3f4f6] p-[2px] rounded-[6px] inline-flex">
                        {tabs.map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`px-[12px] py-[4px] rounded-[4px] text-[12px] font-bold ${activeTab === tab
                                    ? 'bg-white text-[#101828] shadow-sm'
                                    : 'text-[#6a7282] hover:text-[#101828]'
                                    }`}
                            >
                                {tab}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Table Header and List Area */}
                <div className="flex flex-col flex-1 overflow-x-hidden min-h-0">
                    <div className="min-w-[800px] flex flex-col flex-1 min-h-0">
                        {/* Header and List Scroll Container */}
                        <div className="flex flex-col flex-1 overflow-y-auto min-h-0 pb-[12px]">
                            {/* Table Header (Sticky) */}
                            <div className="sticky top-0 z-10 bg-white border-b border-[#f3f4f6] mt-[12px] py-[12px] shrink-0">
                                <div className="mx-[12px]">
                                    <div className="flex items-center px-[18px] text-[#888] text-[13px] font-normal w-full min-w-[776px]">
                                        <div className="w-[60px] shrink-0">순위</div>
                                        <div className="w-[220px] shrink-0">{currentTime}</div>

                                        {/* Flexible shrinking spacer */}
                                        <div className="flex-1 min-w-[10px] max-w-[120px]"></div>

                                        <div className="w-[110px] text-right shrink-0">현재가</div>

                                        {/* Flexible shrinking spacer */}
                                        <div className="flex-1 min-w-[10px] max-w-[120px]"></div>

                                        <div className="w-[110px] text-right shrink-0">등락률</div>

                                        {/* Flexible shrinking spacer */}
                                        <div className="flex-1 min-w-[10px] max-w-[120px]"></div>

                                        <div className="w-[130px] text-right shrink-0">거래대금</div>
                                    </div>
                                </div>
                            </div>

                            {/* 종목 리스트 */}
                            <div className="flex flex-col pt-[4px]">
                                {sortedStocks.map((stock) => (
                                    <div
                                        key={stock.ticker}
                                        className="hover:bg-[#fafafb] transition-colors cursor-pointer rounded-[8px] mx-[12px] shrink-0"
                                    >
                                        <StockRow {...stock} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
};

export default StockList;
