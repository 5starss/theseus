import { ChevronsLeft, ChevronsRight, Wallet, Bot } from "lucide-react";
import type { SidebarMenu } from "./types";
import { useAIStore, type InvestStyle } from "../../../store/useAIStore";
import { useAuthStore } from "../../../store/useAuthStore";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "../../ui/popover";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "../../ui/select";
import { Label } from "../../ui/label";
import { Switch } from "../../ui/switch";

interface IconBarProps {
    isExpanded: boolean;
    activeMenu: SidebarMenu;
    toggleExpand: () => void;
    handleMenuClick: (menu: SidebarMenu) => void;
}

export function IconBar({ isExpanded, activeMenu, toggleExpand, handleMenuClick }: IconBarProps) {
    const { isAIOn, investStyle, toggleAI, setInvestStyle } = useAIStore();
    const isLoggedIn = useAuthStore(state => state.isLoggedIn);

    return (
        <div className="w-16 h-full bg-slate-50 flex flex-col items-center py-4 gap-6 border-l border-slate-100 shrink-0 z-20 shadow-none">
            <button
                onClick={toggleExpand}
                className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all cursor-pointer group"
                title={isExpanded ? "사이드바 접기" : "사이드바 펼치기"}
            >
                {isExpanded ? (
                    <ChevronsRight className="w-6 h-6" />
                ) : (
                    <ChevronsLeft className="w-6 h-6 group-hover:-translate-x-0.5 transition-transform" />
                )}
            </button>

            <div className="w-8 h-[1px] bg-slate-200"></div>

            <button
                onClick={() => handleMenuClick('HOLDINGS')}
                className={`p-2 rounded-xl transition-all cursor-pointer flex flex-col items-center gap-1 group ${(activeMenu === 'HOLDINGS' && isExpanded) ? 'text-blue-600 bg-blue-50' : 'text-slate-500 hover:text-blue-600 hover:bg-blue-50'}`}
                title="보유 종목"
            >
                <Wallet className="w-6 h-6 group-hover:scale-110 transition-transform" />
                <span className="text-[10px] font-bold shrink-0">내 주식</span>
            </button>

            {/* AI Popover Button */}
            <Popover>
                <PopoverTrigger asChild>
                    <button
                        className={`p-2 rounded-xl transition-all cursor-pointer flex flex-col items-center gap-1 group ${isAIOn ? 'text-blue-600 bg-blue-50' : 'text-slate-500 hover:text-blue-600 hover:bg-blue-50'}`}
                        title="AI 분석 설정"
                    >
                        <Bot className={`w-6 h-6 group-hover:scale-110 transition-transform ${isAIOn ? 'animate-pulse' : ''}`} />
                        <span className="text-[10px] font-bold shrink-0 w-12 text-center">AI {isAIOn ? 'ON' : 'OFF'}</span>
                    </button>
                </PopoverTrigger>
                
                <PopoverContent side="left" align="start" alignOffset={8} sideOffset={4} className="w-48 p-4 bg-white border border-slate-100 shadow-xl rounded-2xl z-[100]">
                    {!isLoggedIn ? (
                        <div className="py-2 text-center">
                            <p className="text-slate-400 text-xs font-medium leading-relaxed">
                                로그인이 필요한<br />서비스입니다.
                            </p>
                        </div>
                    ) : (
                        <div className="flex flex-col gap-5">
                            <div className="space-y-2.5">
                                <Label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">투자 성향</Label>
                                <Select
                                    value={investStyle}
                                    onValueChange={(value) => setInvestStyle(value as InvestStyle)}
                                >
                                    <SelectTrigger className="w-full h-9 bg-slate-50 border-slate-100 text-sm font-medium focus:ring-blue-500">
                                        <SelectValue placeholder="성향 선택" />
                                    </SelectTrigger>
                                    <SelectContent position="popper" className="bg-white border-slate-100 shadow-xl z-[110] min-w-40">
                                        <SelectItem value="LONG" className="cursor-pointer hover:bg-slate-50 py-2">장기 투자 (장투)</SelectItem>
                                        <SelectItem value="SHORT" className="cursor-pointer hover:bg-slate-50 py-2">단기 투자 (단타)</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="flex items-center justify-between">
                                <Label htmlFor="ai-toggle" className="text-[11px] font-bold text-slate-400 uppercase tracking-wider cursor-pointer">AI 분석</Label>
                                <Switch 
                                    id="ai-toggle"
                                    checked={isAIOn}
                                    onCheckedChange={toggleAI}
                                />
                            </div>
                        </div>
                    )}
                </PopoverContent>
            </Popover>
        </div>
    );
}
