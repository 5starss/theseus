import { PieChart, History, FileText } from "lucide-react";
import { NavLink } from "react-router-dom";

export const SidebarNav = () => {
    return (
        <div className="bg-white border-r border-[#e5e7eb] h-full relative shrink-0 w-[192px] flex flex-col pt-4 pr-[1px]">
            {/* Header */}
            <div className="border-b border-[#f3f4f6] flex flex-col h-[52.5px] items-start pb-[1px] px-4 w-full">
                <h2 className="font-bold text-[#101828] text-sm leading-5">내 계좌</h2>
            </div>

            {/* Navigation Options */}
            <div className="flex flex-col h-[216px] items-start pt-2 px-2 w-full gap-2">

                {/* 자산 Tab */}
                <NavLink
                    to="/account/asset"
                    className={({ isActive }) =>
                        `flex gap-3 h-10 items-center pl-3 rounded-lg w-full transition-colors ${isActive ? 'bg-[#eff6ff] text-[#155dfc]' : 'bg-transparent text-[#4a5565] hover:bg-slate-50'
                        }`
                    }
                >
                    {({ isActive }) => (
                        <>
                            <PieChart size={18} className={isActive ? 'text-[#155dfc]' : 'text-[#4a5565]'} />
                            <span className="font-medium text-sm">자산</span>
                        </>
                    )}
                </NavLink>

                {/* 거래내역 Tab */}
                <NavLink
                    to="/account/transactions"
                    className={({ isActive }) =>
                        `flex gap-3 h-10 items-center pl-3 rounded-lg w-full transition-colors ${isActive ? 'bg-[#eff6ff] text-[#155dfc]' : 'bg-transparent text-[#4a5565] hover:bg-slate-50'
                        }`
                    }
                >
                    {({ isActive }) => (
                        <>
                            <History size={18} className={isActive ? 'text-[#155dfc]' : 'text-[#4a5565]'} />
                            <span className="font-medium text-sm">거래내역</span>
                        </>
                    )}
                </NavLink>

                {/* 주문내역 Tab */}
                <NavLink
                    to="/account/orders"
                    className={({ isActive }) =>
                        `flex gap-3 h-10 items-center pl-3 rounded-lg w-full transition-colors ${isActive ? 'bg-[#eff6ff] text-[#155dfc]' : 'bg-transparent text-[#4a5565] hover:bg-slate-50'
                        }`
                    }
                >
                    {({ isActive }) => (
                        <>
                            <FileText size={18} className={isActive ? 'text-[#155dfc]' : 'text-[#4a5565]'} />
                            <span className="font-medium text-sm">주문내역</span>
                        </>
                    )}
                </NavLink>

            </div>
        </div>
    );
};
