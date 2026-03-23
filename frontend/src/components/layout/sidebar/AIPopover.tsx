import { useEffect, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { Bot, Loader2, Info } from "lucide-react";
import { useAIStore } from "../../../store/useAIStore";
import { useAuthStore } from "../../../store/useAuthStore";
import { useStockStore } from "../../../store/useStockStore";
import type { AutoTradeStyle } from "../../../api/ai";
import { AIGuideModal } from "./AIGuideModal";

export const AIPopover = () => {
    const {
        isAIOn,
        investStyle,
        isAnalyzing,
        error,
        setInvestStyle,
        toggleAutoTrade,
        fetchConfig,
        setError
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
    }, [isLoggedIn, user, fetchConfig, fetchWatchlist]);

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
                    sideOffset={12} 
                    className="w-64 p-4 rounded-2xl shadow-xl border-slate-100 outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[side=right]:slide-in-from-left-2"
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
