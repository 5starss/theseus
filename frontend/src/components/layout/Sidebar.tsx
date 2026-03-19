import { useState, useEffect, useRef } from "react";
import { useAccountStore } from "../../store/useAccountStore";
import { useAuthStore } from "../../store/useAuthStore";
import type { SidebarMenu } from "./sidebar/types";
import { HoldingsSection } from "./sidebar/HoldingsSection";
import { IconBar } from "./sidebar/IconBar";

export default function Sidebar() {
    const [isExpanded, setIsExpanded] = useState(false);
    const [activeMenu, setActiveMenu] = useState<SidebarMenu>('HOLDINGS');
    const sidebarRef = useRef<HTMLDivElement>(null);

    const isLoggedIn = useAuthStore(state => state.isLoggedIn);
    const { fetchBalance, fetchPositions } = useAccountStore();

    // 사이드바가 열리거나 로그인 상태가 변할 때 데이터 최신화
    useEffect(() => {
        if (isExpanded && isLoggedIn) {
            fetchBalance();
            fetchPositions();
        }
    }, [isExpanded, isLoggedIn, fetchBalance, fetchPositions]);

    const toggleExpand = () => {
        setIsExpanded(!isExpanded);
    };

    const handleMenuClick = (menu: SidebarMenu) => {
        // AI는 이제 Popover로 동작하므로 사이드바 확장에서 제외
        if (menu === 'AI') return;

        if (activeMenu === menu && isExpanded) {
            setIsExpanded(false);
        } else {
            setIsExpanded(true);
            setActiveMenu(menu);
        }
    };

    return (
        <aside
            ref={sidebarRef}
            className={`h-full flex transition-all duration-500 [transition-timing-function:cubic-bezier(0.4,0,0.2,1)] shrink-0 z-50 relative
                ${isExpanded ? 'w-96' : 'w-16'}
            `}
        >
            <div className="flex h-full w-full items-start justify-end overflow-visible">
                {/* Content Area */}
                <div className={`h-full bg-white border-l border-slate-100 transition-all duration-500 [transition-timing-function:cubic-bezier(0.4,0,0.2,1)] overflow-hidden
                    ${isExpanded
                        ? 'opacity-100 w-[320px] pointer-events-auto'
                        : 'opacity-0 w-0 pointer-events-none'}
                `}>
                    {activeMenu === 'HOLDINGS' && <HoldingsSection />}
                </div>

                {/* Icon Bar */}
                <IconBar
                    isExpanded={isExpanded}
                    activeMenu={activeMenu}
                    toggleExpand={toggleExpand}
                    handleMenuClick={handleMenuClick}
                />
            </div>
        </aside>
    );
}
