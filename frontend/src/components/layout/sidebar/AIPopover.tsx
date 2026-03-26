import { useEffect, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Bot, Loader2, Info, CheckCircle2 } from "lucide-react";
import { useAIStore } from "../../../store/useAIStore";
import { useAuthStore } from "../../../store/useAuthStore";
import { useStockStore } from "../../../store/useStockStore";
import { useMarketStore } from "../../../store/useMarketStore";
import type { AutoTradeStyle, AgentStatus } from "../../../api/ai";
import { AIGuideModal } from "./AIGuideModal";

// 개별 종목 분석 상태 카드 컴포넌트
const AgentStatusCard = ({ status }: { status: AgentStatus }) => {
    const { stocks } = useMarketStore();
    const stockName = stocks[status.ticker]?.name || status.ticker;

    const steps = [
        { label: "뉴스", completed: status.newsReceived },
        { label: "퀀트", completed: status.quantReceived },
        { label: "판단", completed: status.judgeReceived }
    ];

    return (
        <div className="bg-white border border-slate-100 rounded-xl p-3 shadow-sm mb-3">
            <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold text-slate-800">{stockName}</span>
                <span className={`text-[10px] font-bold ${status.judgeReceived ? 'text-emerald-500' : 'text-slate-400'}`}>
                    {status.judgeReceived ? '전략 수립 완료' : '전략 수립 중...'}
                </span>
            </div>
            
            <div className="flex items-center gap-1.5">
                {steps.map((step, idx) => (
                    <div key={idx} className="flex-1 flex items-center gap-1 bg-slate-50/50 rounded-lg py-1.5 px-2 border border-slate-50">
                        {step.completed ? (
                            <CheckCircle2 size={12} className="text-emerald-500 shrink-0" />
                        ) : (
                            <Loader2 size={12} className="text-purple-400 animate-spin shrink-0" />
                        )}
                        <span className={`text-[9px] font-bold ${step.completed ? 'text-slate-600' : 'text-slate-400'}`}>
                            {step.label}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export const AIPopover = () => {
    const {
        isAIOn,
        investStyle,
        isAnalyzing,
        agentStatuses,
        error,
        setInvestStyle,
        toggleAutoTrade,
        fetchConfig,
        setError,
        stopPolling
    } = useAIStore();
    const { isLoggedIn, user } = useAuthStore();
    const { watchlist, fetchWatchlist } = useStockStore();
    const [isGuideOpen, setIsGuideOpen] = useState(false);

    // 초기 마운트 시 또는 로그인 상태 변경 시 1회만 설정 가져오기
    useEffect(() => {
        if (isLoggedIn && user) {
            fetchConfig(user.id);
            fetchWatchlist();
        }
        
        // 언마운트 시 폴링 중지
        return () => stopPolling();
    }, [isLoggedIn, user, fetchConfig, fetchWatchlist, stopPolling]);

    const handleToggle = async () => {
        if (!isLoggedIn || !user) return;

        // 켜기 시도 시 관심종목 체크
        if (!isAIOn && watchlist.size === 0) {
            setError("관심종목을 먼저 등록해주세요.");
            return;
        }

        await toggleAutoTrade(user.id, 'AI');
    };

    const handleOpenChange = (open: boolean) => {
        if (!open) {
            setError(null);
        }
    };

    return (
        <>
            <Popover onOpenChange={handleOpenChange}>
                <PopoverTrigger asChild>
                    <button className={`flex flex-col items-center gap-1 p-2 rounded-xl transition-all cursor-pointer group ${isAIOn ? 'bg-purple-100 text-purple-600 shadow-sm' : 'text-slate-500 hover:text-purple-600 hover:bg-purple-50'}`}>
                        <Bot size={24} className={`${isAIOn ? "animate-pulse" : "group-hover:scale-110 transition-transform"}`} />
                        <span className={`text-[10px] font-bold shrink-0 ${isAIOn ? 'text-purple-600' : 'text-slate-500 group-hover:text-purple-600'}`}>AI 매매</span>
                    </button>
                </PopoverTrigger>
                <PopoverContent 
                    side="right" 
                    align="start"
                    alignOffset={-40}
                    sideOffset={12} 
                    className="w-72 p-4 rounded-2xl shadow-xl border-slate-100 outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[side=right]:slide-in-from-left-2"
                    onOpenAutoFocus={(e) => e.preventDefault()}
                    onInteractOutside={(e) => {
                        if (isGuideOpen) {
                            e.preventDefault();
                        }
                    }}
                >
                    <div className="flex flex-col gap-6">
                        <div className="flex flex-col gap-1">
                            <div className="flex items-center justify-between">
                                <h3 className="font-bold text-slate-900">AI 설정</h3>
                                <HoverCard openDelay={150} closeDelay={150}>
                                    <HoverCardTrigger asChild>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setIsGuideOpen(true);
                                            }}
                                            className="p-1 text-slate-300 hover:text-purple-500 transition-colors focus:outline-none"
                                        >
                                            <Info size={20} />
                                        </button>
                                    </HoverCardTrigger>
                                    <HoverCardContent side="top" align="end" className="w-fit py-2 px-3 bg-slate-900 border-slate-800 shadow-xl">
                                        <p className="text-[11px] font-bold text-white whitespace-nowrap">AI 매매 가이드 보기</p>
                                    </HoverCardContent>
                                </HoverCard>
                            </div>
                            <p className="text-xs text-slate-500 leading-relaxed">
                                당신의 투자 성향에 맞춰 AI가 최적의<br />
                                타이밍에 직접 매매를 수행합니다.
                            </p>
                        </div>

                        <div className="flex flex-col gap-3">
                            <Label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">투자 스타일</Label>
                            <Select
                                value={investStyle}
                                onValueChange={(val) => setInvestStyle(val as AutoTradeStyle)}
                                disabled={isAIOn || isAnalyzing}
                            >
                                <SelectTrigger className="w-full h-10 border-slate-100 bg-slate-50 rounded-xl focus:ring-purple-200">
                                    <SelectValue placeholder="스타일 선택" />
                                </SelectTrigger>
                                <SelectContent position="popper" sideOffset={4} className="rounded-xl border-slate-100 w-[var(--radix-select-trigger-width)]">
                                    <SelectItem value="LONG" className="text-xs font-bold py-2.5 cursor-pointer rounded-lg m-1">장기 투자 (LONG)</SelectItem>
                                    <SelectItem value="SHORT" className="text-xs font-bold py-2.5 cursor-pointer rounded-lg m-1">단기 스윙 (SHORT)</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="flex items-center justify-between bg-slate-50 p-3 rounded-xl border border-slate-100 transition-all">
                            <div className="flex flex-col">
                                <span className="text-xs font-bold text-slate-700">AI 자동 매매</span>
                                <span className="text-[10px] text-slate-400 font-medium">{isAIOn ? '현재 가동 중' : '비활성 상태'}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                {isAnalyzing ? (
                                    <Loader2 size={16} className="animate-spin text-purple-600" />
                                ) : (
                                    <>
                                        <span className={`text-[10px] font-black w-8 text-center transition-colors ${isAIOn ? 'text-purple-600' : 'text-slate-300'}`}>
                                            {isAIOn ? 'ON' : 'OFF'}
                                        </span>
                                        <Switch
                                            checked={isAIOn}
                                            onCheckedChange={handleToggle}
                                            disabled={!isLoggedIn || isAnalyzing}
                                            className="data-[state=checked]:bg-purple-600"
                                        />
                                    </>
                                )}
                            </div>
                        </div>

                        {/* AI 실시간 분석 상태 섹션 */}
                        {isAIOn && (
                            <div className="flex flex-col gap-3">
                                <Label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        실시간 분석 리포트
                                        <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                                    </div>
                                    <span className="text-[9px] text-slate-300 font-medium lowercase">
                                        {new Date().getHours() < 12 ? 'morning slot' : 'afternoon slot'}
                                    </span>
                                </Label>
                                <ScrollArea className="h-64 pr-2">
                                    {(() => {
                                        const currentSlot = new Date().getHours() < 12 ? 'morning' : 'afternoon';
                                        const filtered = agentStatuses.filter(s => s.strategySlot === currentSlot);
                                        
                                        if (filtered.length > 0) {
                                            return filtered.map((status, idx) => (
                                                <AgentStatusCard key={idx} status={status} />
                                            ));
                                        }
                                        
                                        return (
                                            <div className="flex flex-col items-center justify-center h-32 bg-slate-50/50 rounded-xl border border-dashed border-slate-200">
                                                <Loader2 size={20} className="text-purple-300 animate-spin mb-2" />
                                                <p className="text-[10px] text-slate-400 font-medium">분석 데이터를 수신 중입니다...</p>
                                            </div>
                                        );
                                    })()}
                                </ScrollArea>
                            </div>
                        )}

                        {error && (
                            <p className="text-[10px] text-red-500 font-bold text-center bg-red-50 py-2 rounded-lg animate-in fade-in slide-in-from-top-1 duration-200">
                                {error}
                            </p>
                        )}

                        {!isLoggedIn && (
                            <p className="text-[10px] text-slate-400 font-bold text-center border border-dashed border-slate-200 py-2 rounded-lg animate-in fade-in slide-in-from-top-1 duration-200">
                                로그인이 필요합니다.
                            </p>
                        )}
                    </div>
                </PopoverContent>
            </Popover>

            {/* AI 가이드 모달 */}
            <AIGuideModal
                isOpen={isGuideOpen}
                onClose={() => setIsGuideOpen(false)}
            />
        </>
    );
};
