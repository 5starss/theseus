import { Outlet } from "react-router-dom";
import { SidebarNav } from "../components/account/SidebarNav";

export default function Account() {

    return (
        <div className="w-full h-full flex bg-white overflow-hidden">
            {/* Left Sidebar Navigation */}
            <SidebarNav />

            {/* Main Content Area */}
            <div className="flex-1 h-full min-w-0 bg-white">
                <Outlet />
            </div>
        </div>
    );
}
