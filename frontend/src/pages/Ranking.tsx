import { useEffect, useState, memo } from "react";
import { rankingApi } from "../api/ranking";
import type { RankingSnapshotResponse } from "../api/ranking";
import { useAuthStore } from "../store/useAuthStore";
import { ChevronLeft, ChevronRight, Calendar, Search, Trophy } from "lucide-react";

// 검색바 컴포넌트 분리 (타이핑 시 전체 리렌더링 방지)
const SearchBar = memo(({ onSearch }: { onSearch: (query: string) => void }) => {
    const [localQuery, setLocalQuery] = useState("");

    useEffect(() => {
        const timer = setTimeout(() => {
            onSearch(localQuery);
        }, 300);
        return () => clearTimeout(timer);
    }, [localQuery, onSearch]);

    return (
        <div className="relative w-full max-w-[280px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#99a1af]" />
            <input 
                type="text" 
                placeholder="사용자 닉네임 검색" 
                value={localQuery}
                onChange={(e) => setLocalQuery(e.target.value)}
                className="w-full h-10 pl-9 pr-4 bg-white border border-[#f3f4f6] rounded-xl text-sm outline-none focus:ring-2 focus:ring-[#101828]/5 shadow-sm transition-all placeholder:text-[#d1d5db]"
            />
        </div>
    );
});

export default function Ranking() {
    const [data, setData] = useState<RankingSnapshotResponse | null>(null);
    const [page, setPage] = useState(0);
    const [loading, setLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const user = useAuthStore(state => state.user);

    const fetchRankings = async (targetPage: number, nickname?: string) => {
        setLoading(true);
        try {
            const response = await rankingApi.getRankings(targetPage, 10, nickname);
            if (response.data.isSuccess) {
                setData(response.data.result);
                setPage(targetPage);
            }
        } catch (error) {
            console.error("Failed to fetch rankings:", error);
        } finally {
            setLoading(false);
        }
    };

    // 초기 로딩 및 검색어 변경 시 동작
    useEffect(() => {
        fetchRankings(0, searchQuery);
    }, [searchQuery]);

    const myRank = data?.myRanking;
    const rankingList = data?.rankings.content || [];
    const totalPages = data?.rankings.totalPages || 0;
    const latestDate = data?.rankings.content?.[0]?.rankDate || new Date().toISOString().split('T')[0];

    const handlePageChange = (targetPage: number) => {
        fetchRankings(targetPage, searchQuery);
    };

    return (
        <div className="w-full min-h-full bg-[#f2f4f7] p-6 flex flex-col gap-6 overflow-y-auto font-sans">
            <div className="flex flex-col gap-6 max-w-[1000px] mx-auto w-full mt-4">
                
                {/* Header */}
                <div className="flex flex-col gap-2 px-1">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 bg-[#101828] rounded-xl flex items-center justify-center shadow-lg shadow-[#101828]/10 shrink-0">
                            <Trophy className="w-5 h-5 text-white" />
                        </div>
                        <h1 className="text-2xl font-black text-[#101828] tracking-tight">투자 랭킹</h1>
                    </div>
                    <p className="text-[13px] text-[#99a1af] font-bold">
                        전체 투자자의 통합 수익률(ROI) 기반 실시간 순위
                    </p>
                </div>

                {/* My Ranking Card */}
                {user && (
                    <div className="bg-white rounded-[24px] border border-[#f3f4f6] shadow-[0_1px_2px_rgba(0,0,0,0.02)] p-6">
                        <h2 className="text-[10px] font-black text-[#d1d5db] mb-6 text-center uppercase tracking-[0.2em]">Personal Performance</h2>
                        <div className="grid grid-cols-4 divide-x divide-[#f3f4f6]">
                            <div className="flex flex-col items-center justify-center">
                                <span className="text-[12px] font-bold text-[#99a1af] mb-1.5">내 순위</span>
                                <span className="text-2xl font-black text-[#101828]">{myRank ? `${myRank.rank}위` : "-"}</span>
                            </div>
                            <div className="flex flex-col items-center justify-center">
                                <span className="text-[12px] font-bold text-[#99a1af] mb-1.5">수익률(ROI)</span>
                                <span className={`text-xl font-black ${myRank && myRank.roi >= 0 ? 'text-[#ff4d4f]' : 'text-[#1890ff]'}`}>
                                    {myRank ? (myRank.roi >= 0 ? `+${myRank.roi.toFixed(2)}%` : `${myRank.roi.toFixed(2)}%`) : "0.00%"}
                                </span>
                            </div>
                            <div className="flex flex-col items-center justify-center px-4">
                                <span className="text-[12px] font-bold text-[#99a1af] mb-1.5 text-center">닉네임</span>
                                <span className="text-base font-bold text-[#101828] truncate w-full text-center">{user.name}</span>
                            </div>
                            <div className="flex flex-col items-center justify-center">
                                <span className="text-[12px] font-bold text-[#99a1af] mb-1.5">상위 퍼센트</span>
                                <span className="text-base font-bold text-[#101828]">
                                    {myRank && data?.rankings.totalElements 
                                        ? `${((myRank.rank / data.rankings.totalElements) * 100).toFixed(1)}%` 
                                        : "-"}
                                </span>
                            </div>
                        </div>
                    </div>
                )}

                {/* Sub Bar & Tables Section */}
                <div className="flex flex-col gap-2.5">
                    <div className="flex items-end justify-between px-1">
                        <div className="flex items-center gap-1.5 text-[13px] text-[#99a1af] font-bold pb-1">
                            <Calendar className="w-3.5 h-3.5" />
                            {latestDate} 기준
                        </div>

                        <SearchBar onSearch={setSearchQuery} />
                    </div>

                    <div className="bg-white border border-[#f3f4f6] rounded-[24px] shadow-[0_1px_4px_rgba(0,0,0,0.02)] overflow-hidden min-h-[580px] flex flex-col">
                        <table className="w-full text-left border-collapse table-fixed">
                            <thead className="bg-[#f8f9fa] border-b border-[#f3f4f6]">
                                <tr>
                                    <th className="px-6 py-4 text-[12px] font-bold text-[#99a1af] text-center w-[80px]">순위</th>
                                    <th className="px-4 py-4 text-[12px] font-bold text-[#99a1af]">투자자</th>
                                    <th className="px-6 py-4 text-[12px] font-bold text-[#99a1af] text-right w-[150px]">수익률(ROI)</th>
                                </tr>
                            </thead>
                            <tbody className={`divide-y divide-[#f3f4f6] transition-opacity duration-150 ${loading ? 'opacity-40' : 'opacity-100'}`}>
                                {loading && !data ? (
                                    Array.from({ length: 10 }).map((_, i) => (
                                        <tr key={`skeleton-${i}`} className="animate-pulse">
                                            <td className="px-6 py-4"><div className="h-6 w-8 bg-slate-100 rounded-lg mx-auto" /></td>
                                            <td className="px-4 py-4"><div className="flex items-center gap-3"><div className="w-8 h-8 rounded-full bg-slate-100" /><div className="h-4 w-24 bg-slate-100 rounded" /></div></td>
                                            <td className="px-6 py-4"><div className="h-4 w-16 bg-slate-100 rounded ml-auto" /></td>
                                        </tr>
                                    ))
                                ) : (
                                    rankingList.map((row) => {
                                        const isMe = row.userId === user?.id;
                                        return (
                                            <tr key={`${row.rank}-${row.nickname}`} className={`transition-colors cursor-default ${isMe ? 'bg-[#f0f7ff]' : 'hover:bg-slate-50/50'}`}>
                                                <td className="px-6 py-4">
                                                    <div className="flex justify-center items-center">
                                                        {row.rank === 1 ? <span className="text-xl">👑</span> : 
                                                         row.rank === 2 ? <span className="text-xl">🥈</span> : 
                                                         row.rank === 3 ? <span className="text-xl">🥉</span> : 
                                                         <span className="text-sm font-bold text-[#101828] opacity-40">{row.rank}</span>}
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4 truncate">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 rounded-full bg-[#f3f4f6] flex items-center justify-center text-[10px] text-[#99a1af] font-bold border border-[#f3f4f6] uppercase shrink-0">
                                                            {row.nickname.charAt(0)}
                                                        </div>
                                                        <span className="text-[15px] text-[#101828] font-bold truncate">{row.nickname}</span>
                                                        {isMe && <span className="text-[9px] bg-[#101828] text-white px-1.5 py-0.5 rounded-md font-black ml-1 shrink-0">ME</span>}
                                                    </div>
                                                </td>
                                                <td className={`px-6 py-4 text-right font-bold text-[15px] ${row.roi >= 0 ? 'text-[#ff4d4f]' : 'text-[#1890ff]'}`}>
                                                    {row.roi > 0 ? '+' : ''}{row.roi.toFixed(2)}%
                                                </td>
                                            </tr>
                                        )
                                    })
                                )}
                                {!loading && rankingList.length === 0 && (
                                    <tr>
                                        <td colSpan={3} className="px-6 py-24 text-center text-[#99a1af] font-bold text-sm">
                                            {searchQuery ? `"${searchQuery}" 유저를 찾을 수 없습니다.` : "랭킹 데이터가 존재하지 않습니다."}
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>

                        {/* Pagination Section - Always at bottom */}
                        <div className="mt-auto">
                            {totalPages > 1 && (
                                <div className="flex justify-center items-center gap-2 py-4 bg-white border-t border-[#f3f4f6]">
                                    <button
                                        disabled={page === 0 || loading}
                                        onClick={() => handlePageChange(page - 1)}
                                        className={`p-2 rounded-xl transition-colors ${page === 0 ? 'text-[#d1d5db] cursor-not-allowed' : 'text-[#6a7282] hover:bg-slate-50'}`}
                                    >
                                        <ChevronLeft className="w-4 h-4" />
                                    </button>

                                    {Array.from({ length: totalPages })
                                        .map((_, i) => i)
                                        .filter(i => {
                                            const start = Math.max(0, Math.min(page - 2, totalPages - 5));
                                            const end = Math.min(totalPages - 1, start + 4);
                                            return i >= start && i <= end;
                                        })
                                        .map(i => (
                                            <button
                                                key={i}
                                                onClick={() => handlePageChange(i)}
                                                className={`w-8 h-8 flex items-center justify-center rounded-xl font-bold text-sm transition-all ${
                                                    page === i ? 'bg-[#101828] text-white shadow-md' : 'text-[#6a7282] hover:bg-slate-100'
                                                }`}
                                            >
                                                {i + 1}
                                            </button>
                                        ))}

                                    <button
                                        disabled={page >= totalPages - 1 || loading}
                                        onClick={() => handlePageChange(page + 1)}
                                        className={`p-2 rounded-xl transition-colors ${page >= totalPages - 1 ? 'text-[#d1d5db] cursor-not-allowed' : 'text-[#6a7282] hover:bg-slate-50'}`}
                                    >
                                        <ChevronRight className="w-4 h-4" />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
