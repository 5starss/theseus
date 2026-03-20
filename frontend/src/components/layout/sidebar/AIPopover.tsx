import { useEffect } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Bot, Loader2 } from "lucide-react";
import { useAIStore } from "../../../store/useAIStore";
import { useAuthStore } from "../../../store/useAuthStore";
import type { AutoTradeStyle } from "../../../api/ai";

export const AIPopover = () => {
    const { 
        isAIOn, 
        investStyle, 
        isAnalyzing, 
        error,
        setInvestStyle, 
        toggleAutoTrade,
        fetchConfig 
    } = useAIStore();
    const { isLoggedIn, user } = useAuthStore();

    // 초기 마운트 시 또는 로그인 상태 변경 시 1회만 설정 가져오기
    useEffect(() => {
        if (isLoggedIn && user) {
            fetchConfig(user.id);
        }
    }, [isLoggedIn, user, fetchConfig]);

    const handleToggle = async () => {
        if (!isLoggedIn || !user) return;
        await toggleAutoTrade(user.id, 'AI');
    };

    return (
        <Popover>
            <PopoverTrigger asChild>
                <button className={`flex flex-col items-center gap-1 p-2 rounded-xl transition-all cursor-pointer group ${isAIOn ? 'bg-purple-100 text-purple-600 shadow-sm' : 'text-slate-500 hover:text-purple-600 hover:bg-purple-50'}`}>
                    <Bot size={24} className={`${isAIOn ? "animate-pulse" : "group-hover:scale-110 transition-transform"}`} />
                    <span className={`text-[10px] font-bold shrink-0 ${isAIOn ? 'text-purple-600' : 'text-slate-500 group-hover:text-purple-600'}`}>AI 매매</span>
                </button>
            </PopoverTrigger>
            <PopoverContent side="right" sideOffset={12} className="w-64 p-4 rounded-2xl shadow-xl border-slate-100">
                <div className="flex flex-col gap-6">
                    <div className="flex flex-col gap-1">
                        <h3 className="font-bold text-slate-900">AI 설정</h3>
                        <p className="text-xs text-slate-500 leading-relaxed">당신의 투자 성향에 맞춰 AI가 최적의 타이밍에 직접 매매를 수행합니다.</p>
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
                            <SelectContent className="rounded-xl border-slate-100">
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
                        <p className="text-[10px] text-red-500 font-bold text-center bg-red-50 py-2 rounded-lg">
                            {error}
                        </p>
                    )}

                    {!isLoggedIn && (
                        <p className="text-[10px] text-slate-400 font-bold text-center border border-dashed border-slate-200 py-2 rounded-lg">
                            로그인이 필요합니다.
                        </p>
                    )}
                </div>
            </PopoverContent>
        </Popover>
    );
};
