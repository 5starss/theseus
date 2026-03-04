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
    const sortedStocks = React.useMemo(() => {
        const stockArray = Object.values(stocksMap);

        return stockArray.sort((a, b) => {
            switch (activeTab) {
                case '현재가':
                    return b.price - a.price; 
                case '등락률':
                    return b.changeRate - a.changeRate;
                case '종목명':
                    return a.name.localeCompare(b.name, 'ko-KR'); 
                case '거래량':
                    return b.volume - a.volume; 
                case '거래대금':
                default:
                    return (b.price * b.volume) - (a.price * a.volume);
            }
        }).map((stock, index) => ({
            ...stock,
            rank: index + 1 // 정렬된 순서에 따라 rank 업데이트
        }));
    }, [stocksMap, activeTab]);

    return (
        <div className="w-full h-full flex flex-col items-center bg-[#f9fafb] p-[12px]">
            <div className="w-full bg-white border border-[#f3f4f6] rounded-[12px] shadow-sm flex flex-col">

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

                {/* Table Header */}
                <div className="flex items-center px-[30px] py-[12px] text-[#888] text-[13px] font-normal border-b border-[#f3f4f6] mt-[12px]">
                    <div className="w-[60px]">순위</div>
                    <div className="w-[311px]">오늘 10:09 기준</div>
                    <div className="w-[120px] text-right">현재가</div>
                    <div className="w-[120px] text-right">등락률</div>
                    <div className="w-[60px]"></div>
                    <div className="w-[194px]">거래대금</div>
                    <div className="flex-1"></div>
                    <div className="w-[116px]">거래비율</div>
                </div>

                {/* 종목 리스트 */}
                <div className="flex flex-col pb-[12px] pt-[4px]">
                    {sortedStocks.map((stock) => (
                        <div
                            key={stock.code}
                            className="hover:bg-[#fafafb] transition-colors cursor-pointer rounded-[8px] mx-[12px]"
                        >
                            <StockRow {...stock} />
                        </div>
                    ))}
                </div>

            </div>
        </div>
    );
};

export default StockList;
