import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { EyeIcon, EyeOffIcon, ArrowLeftIcon, Loader2Icon, ChevronDownIcon } from "lucide-react";
import { authApi } from "@/api/auth";
import { getErrorMessage } from "@/utils/errorMessages";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";

export default function SignupPage() {
    const navigate = useNavigate();
    const [nickname, setNickname] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [investmentStyle, setInvestmentStyle] = useState<"BALANCED" | "GROWTH" | "AGGRESSIVE">("BALANCED");

    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    const handleStyleSelect = (val: "BALANCED" | "GROWTH" | "AGGRESSIVE") => {
        setInvestmentStyle(val);
        setIsDropdownOpen(false);
    };

    const handleSignup = async (e: React.FormEvent) => {
        e.preventDefault();
        setErrorMessage("");

        if (password !== confirmPassword) {
            setErrorMessage("비밀번호가 일치하지 않습니다.");
            return;
        }

        try {
            setIsLoading(true);
            await authApi.signup({
                email,
                password,
                nickname,
                investmentStyle
            });
            // 회원가입 성공
            navigate("/login");
        } catch (error: unknown) {
            // 더 견고한 에러 체크: ApiError 혹은 code 프로퍼티가 있는 객체인 경우
            if (error && typeof error === 'object' && 'code' in error && typeof (error as any).code === 'string') {
                const fallbackMsg = (error as any).message;
                setErrorMessage(getErrorMessage((error as any).code, fallbackMsg));
            } else if (error instanceof Error) {
                setErrorMessage(error.message);
            } else {
                setErrorMessage("회원가입 중 오류가 발생했습니다.");
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div
            className="min-h-screen flex flex-col items-center justify-center p-4 relative"
            style={{ backgroundImage: "linear-gradient(139.619deg, rgb(239, 246, 255) 0%, rgb(255, 255, 255) 50%, rgb(239, 246, 255) 100%)" }}
        >
            {/*헤더 / 로고 (카드 밖 세션) */}
            <div className="flex items-center gap-2 mb-[40px] z-10 transition-transform hover:scale-105 cursor-pointer" onClick={() => navigate("/")}>
                <div className="w-[48px] h-[48px] bg-[#155dfc] text-white flex items-center justify-center font-bold rounded-2xl shadow-lg text-2xl">
                    S
                </div>
                <span className="font-bold text-[30px] tracking-tight text-slate-900">싸피증권</span>
            </div>

            {/* 회원가입 카드 */}
            <div className="w-full max-w-[560px] bg-white rounded-3xl shadow-[0px_10px_50px_0px_rgba(0,0,0,0.1)] border border-slate-100 px-[40px] pt-[30px] pb-[50px] z-10 relative">

                {/* 뒤로가기 버튼 */}
                <div className="flex items-center mb-[10px] ml-[-4px]">
                    <button type="button" onClick={() => navigate("/login")} className="flex items-center gap-[4px] text-[14px] font-medium text-[#4a5565] hover:text-[#101828] transition-colors bg-transparent border-none p-0 cursor-pointer outline-none">
                        <ArrowLeftIcon className="w-4 h-4" />
                        로그인으로 돌아가기
                    </button>
                </div>

                <div className="flex flex-col items-center gap-[8px] mb-[45px]">
                    <h1 className="text-[24px] font-bold text-slate-900 tracking-tight">회원가입</h1>
                    <p className="text-[16px] font-normal text-slate-500">새로운 계정을 만들어보세요</p>
                </div>

                <form onSubmit={handleSignup} className="flex flex-col gap-[20px]">

                    {/* 이메일 입력 */}
                    <div className="flex flex-col gap-[8px]">
                        <label className="text-[14px] font-bold text-slate-700">
                            이메일 계정 <span className="text-[#fb2c36]">*</span>
                        </label>
                        <input
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder="example@email.com"
                            className="w-full px-[16px] py-[14px] bg-[#f9fafb] border border-[#e5e7eb] rounded-xl text-[16px] outline-none focus:border-[#155dfc] focus:ring-1 focus:ring-[#155dfc] transition-all font-normal placeholder:text-[rgba(0,0,0,0.4)] text-slate-800"
                            required
                            disabled={isLoading}
                        />
                    </div>

                    {/* 닉네임 입력 */}
                    <div className="flex flex-col gap-[8px]">
                        <label className="text-[14px] font-bold text-slate-700">
                            닉네임 <span className="text-[#fb2c36]">*</span>
                        </label>
                        <input
                            type="text"
                            value={nickname}
                            onChange={e => setNickname(e.target.value)}
                            placeholder="사용하실 닉네임을 입력하세요"
                            className="w-full px-[16px] py-[14px] bg-[#f9fafb] border border-[#e5e7eb] rounded-xl text-[16px] outline-none focus:border-[#155dfc] focus:ring-1 focus:ring-[#155dfc] transition-all font-normal placeholder:text-[rgba(0,0,0,0.4)] text-slate-800"
                            required
                            disabled={isLoading}
                        />
                    </div>

                    {/* 비밀번호 입력 */}
                    <div className="flex flex-col gap-[8px]">
                        <label className="text-[14px] font-bold text-slate-700">
                            비밀번호 <span className="text-[#fb2c36]">*</span>
                        </label>
                        <div className="relative">
                            <input
                                type={showPassword ? "text" : "password"}
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                placeholder="8자 이상 입력하세요"
                                className="w-full pl-[16px] pr-[48px] py-[14px] bg-[#f9fafb] border border-[#e5e7eb] rounded-xl text-[16px] outline-none focus:border-[#155dfc] focus:ring-1 focus:ring-[#155dfc] transition-all font-normal placeholder:text-[rgba(0,0,0,0.4)] text-slate-800"
                                required
                                disabled={isLoading}
                            />
                            <Button
                                variant="ghost"
                                size="icon"
                                type="button"
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 hover:bg-transparent transition-colors h-8 w-8"
                                onClick={() => setShowPassword(!showPassword)}
                                disabled={isLoading}
                            >
                                {showPassword ? <EyeOffIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                            </Button>
                        </div>
                    </div>

                    {/* 비밀번호 확인 */}
                    <div className="flex flex-col gap-[8px]">
                        <label className="text-[14px] font-bold text-slate-700">
                            비밀번호 확인 <span className="text-[#fb2c36]">*</span>
                        </label>
                        <div className="relative">
                            <input
                                type={showConfirmPassword ? "text" : "password"}
                                value={confirmPassword}
                                onChange={e => setConfirmPassword(e.target.value)}
                                placeholder="비밀번호를 다시 입력하세요"
                                className="w-full pl-[16px] pr-[48px] py-[14px] bg-[#f9fafb] border border-[#e5e7eb] rounded-xl text-[16px] outline-none focus:border-[#155dfc] focus:ring-1 focus:ring-[#155dfc] transition-all font-normal placeholder:text-[rgba(0,0,0,0.4)] text-slate-800"
                                required
                                disabled={isLoading}
                            />
                            <Button
                                variant="ghost"
                                size="icon"
                                type="button"
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 hover:bg-transparent transition-colors h-8 w-8"
                                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                disabled={isLoading}
                            >
                                {showConfirmPassword ? <EyeOffIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                            </Button>
                        </div>
                    </div>

                    {/* 투자 성향 선택 */}
                    <div className="flex flex-col gap-[8px] mb-[10px]">
                        <label className="text-[14px] font-bold text-slate-700">
                            투자 성향 <span className="text-[#fb2c36]">*</span>
                        </label>
                        <Popover open={isDropdownOpen} onOpenChange={setIsDropdownOpen} modal={false}>
                            <PopoverTrigger asChild>
                                <button
                                    type="button"
                                    disabled={isLoading}
                                    className="w-full flex items-center justify-between px-[16px] py-[14px] bg-[#f9fafb] border border-[#e5e7eb] rounded-xl text-[16px] outline-none focus:border-[#155dfc] focus:ring-1 focus:ring-[#155dfc] transition-all font-normal text-slate-800"
                                >
                                    <span>
                                        {investmentStyle === "BALANCED" ? "안정형" :
                                            investmentStyle === "GROWTH" ? "성장형" : "공격형"}
                                    </span>
                                    <ChevronDownIcon className="w-5 h-5 text-slate-400 opacity-70" />
                                </button>
                            </PopoverTrigger>
                            <PopoverContent
                                className="w-[var(--radix-popover-trigger-width)] p-1 rounded-xl bg-white shadow-lg border-slate-100"
                                align="start"
                                sideOffset={4}
                            >
                                <div
                                    onClick={() => handleStyleSelect("BALANCED")}
                                    className="w-full px-4 py-3 hover:bg-slate-50 cursor-pointer rounded-lg text-[15px] font-medium text-slate-800"
                                >
                                    안정형
                                </div>
                                <div
                                    onClick={() => handleStyleSelect("GROWTH")}
                                    className="w-full px-4 py-3 hover:bg-slate-50 cursor-pointer rounded-lg text-[15px] font-medium text-slate-800"
                                >
                                    성장형
                                </div>
                                <div
                                    onClick={() => handleStyleSelect("AGGRESSIVE")}
                                    className="w-full px-4 py-3 hover:bg-slate-50 cursor-pointer rounded-lg text-[15px] font-medium text-slate-800"
                                >
                                    공격형
                                </div>
                            </PopoverContent>
                        </Popover>
                    </div>

                    {/* 에러 메시지 */}
                    {errorMessage && (
                        <div className="text-[#fb2c36] text-[14px] font-medium text-center">
                            {errorMessage}
                        </div>
                    )}

                    {/* 회원가입 완료 버튼 */}
                    <Button type="submit" disabled={isLoading} className="w-full h-[52px] bg-[#155dfc] hover:bg-[#124bc9] text-white font-bold rounded-xl text-[16px] shadow-lg mb-[10px]">
                        {isLoading ? <Loader2Icon className="w-5 h-5 animate-spin" /> : "회원가입 완료"}
                    </Button>

                    {/* 로그인 링크 */}
                    <div className="flex justify-center items-center gap-[4px]">
                        <span className="text-[14px] font-normal text-[#4a5565]">이미 계정이 있으신가요?</span>
                        <Link to="/login" className="text-[14px] font-bold text-[#155dfc] hover:text-[#124bc9] transition-colors">
                            로그인하기
                        </Link>
                    </div>

                </form>
            </div>
        </div>
    );
}
