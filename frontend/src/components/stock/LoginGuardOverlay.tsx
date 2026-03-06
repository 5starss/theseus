import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";

interface LoginGuardOverlayProps {
    message?: string;
    buttonText?: string;
}

// 로그인 필요 시 오버레이 컴포넌트
export function LoginGuardOverlay({
    message = "로그인이 필요한 서비스입니다",
    buttonText = "로그인하기"
}: LoginGuardOverlayProps) {
    const location = useLocation();

    return (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-white/60 backdrop-blur-sm">
            <span className="text-sm font-semibold text-slate-700 mb-3">{message}</span>
            <Button asChild className="h-8 px-4 bg-[#155dfc] hover:bg-[#124bc9] text-white text-xs font-bold rounded-md transition-colors shadow-sm">
                <Link to="/login" state={{ from: location }}>{buttonText}</Link>
            </Button>
        </div>
    );
}
