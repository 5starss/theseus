import { ChevronsLeft, ChevronsRight, Wallet } from "lucide-react";
import type { SidebarMenu } from "./types";
import { AIPopover } from "./AIPopover";

interface IconBarProps {
    isExpanded: boolean;
    activeMenu: SidebarMenu;
    toggleExpand: () => void;
    handleMenuClick: (menu: SidebarMenu) => void;
}

export function IconBar({ isExpanded, activeMenu, toggleExpand, handleMenuClick }: IconBarProps) {
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

            {/* AI Popover Component */}
            <AIPopover />
        </div>
    );
}
