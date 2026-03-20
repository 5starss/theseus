import { PieChart, History, FileText } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAccountStore } from "../../store/useAccountStore";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { AccountType } from "../../api/account";

export const SidebarNav = () => {
    const { currentAccountType, setAccountType } = useAccountStore();

    return (
        <div className="bg-white border-r border-[#e5e7eb] h-full relative shrink-0 w-[192px] flex flex-col pt-4 pr-[1px]">
            {/* Header */}
            <div className="flex flex-col items-start px-3 w-full mb-4">
                <h2 className="font-bold text-[#101828] text-[11px] uppercase tracking-wider mb-2 px-1 opacity-50">계좌 선택</h2>

                <Select
                    value={currentAccountType}
                    onValueChange={(val) => setAccountType(val as AccountType)}
                >
                    <SelectTrigger className="w-full h-10 border-[#f3f4f6] bg-[#f9fafb] px-3 shadow-none focus:ring-0 rounded-lg transition-all hover:bg-slate-100 hover:border-slate-200 border-solid border-[0.5px]">
                        <div className="flex items-center gap-2 overflow-hidden text-left">
                            <div className={`w-1.5 h-1.5 shrink-0 rounded-full ${currentAccountType === 'USER' ? 'bg-[#fb2c36]' : 'bg-purple-500'}`}></div>
                            <SelectValue />
                        </div>
                    </SelectTrigger>
                    <SelectContent
                        position="popper"
                        sideOffset={4}
                        align="start"
                        className="rounded-xl shadow-md border-[#f3f4f6] bg-white z-[100] w-[calc(192px-24px)] overflow-hidden"
                    >
                        <SelectItem
                            value="USER"
                            className="text-[13px] font-bold py-2.5 pr-3 cursor-pointer rounded-lg hover:bg-slate-50 focus:bg-slate-50 transition-colors w-full relative text-[#4a5565]"
                        >
                            기본계좌
                        </SelectItem>
                        <SelectItem
                            value="AI"
                            className="text-[13px] font-bold py-2.5 pr-3 cursor-pointer rounded-lg hover:bg-slate-50 focus:bg-slate-50 transition-colors w-full relative text-[#4a5565]"
                        >
                            AI계좌
                        </SelectItem>
                    </SelectContent>
                </Select>
            </div>

            <div className="border-b border-[#f3f4f6] w-full mb-2"></div>

            {/* Navigation Options */}
            <div className="flex flex-col h-auto items-start pt-2 px-2 w-full gap-2">

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
