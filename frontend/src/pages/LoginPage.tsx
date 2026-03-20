import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/useAuthStore";
import { Button } from "@/components/ui/button";
import { EyeIcon, EyeOffIcon } from "lucide-react";

import { authApi } from "../api/auth";
import { getErrorMessage } from "../utils/errorMessages";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");

    const login = useAuthStore(state => state.login);
    const navigate = useNavigate();
    const location = useLocation();

    // 로그인 처리
    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setErrorMessage("");

        if (email && password) {
            setIsLoading(true);
            try {
                const response = await authApi.login({ email, password });
                login(response.userId, email, response.accessToken, response.nickname);

                // ProtectedRoute 등에서 넘겨준 이전 페이지 주소가 있다면 그곳으로, 없다면 홈으로 이동
                const from = location.state?.from?.pathname || "/";
                navigate(from, { replace: true });
            } catch (error: unknown) {
                // 더 견고한 에러 체크: ApiError 혹은 code 프로퍼티가 있는 객체인 경우
                if (error && typeof error === 'object' && 'code' in error && typeof (error as any).code === 'string') {
                    const fallbackMsg = (error as any).message;
                    setErrorMessage(getErrorMessage((error as any).code, fallbackMsg));
                } else if (error instanceof Error) {
                    setErrorMessage(error.message);
                } else {
                    setErrorMessage("로그인 중 오류가 발생했습니다.");
                }
            } finally {
                setIsLoading(false);
            }
        }
    };

    return (
        <div
            className="min-h-screen flex flex-col items-center justify-center p-4 relative"
            style={{ backgroundImage: "linear-gradient(148.161deg, rgb(239, 246, 255) 0%, rgb(255, 255, 255) 50%, rgb(239, 246, 255) 100%)" }}
        >
            {/* 헤더 / 로고 (카드 밖 세션) */}
            <div className="flex items-center gap-2 mb-[40px] z-10 transition-transform hover:scale-105 cursor-pointer" onClick={() => navigate("/")}>
                <div className="w-[48px] h-[48px] bg-[#155dfc] text-white flex items-center justify-center font-bold rounded-2xl shadow-lg text-2xl">
                    S
                </div>
                <span className="font-bold text-[30px] tracking-tight text-slate-900">싸피증권</span>
            </div>

            {/* 로그인 카드 */}
            <div className="w-full max-w-[560px] bg-white rounded-3xl shadow-[0px_10px_50px_0px_rgba(0,0,0,0.1)] border border-slate-100 px-[40px] pt-[40px] pb-[40px] z-10 relative">

                <div className="flex flex-col items-center gap-[8px] mb-[32px] text-center">
                    <h1 className="text-[24px] font-bold text-slate-900 tracking-tight">로그인</h1>
                    <p className="text-[16px] font-normal text-slate-500">계정 정보를 입력해주세요</p>
                </div>

                <form onSubmit={handleLogin} className="flex flex-col">

                    {/* 이메일 입력 */}
                    <div className="flex flex-col gap-[8px] mb-[16px]">
                        <label className="text-[14px] font-bold text-slate-700">이메일</label>
                        <input
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder="이메일을 입력하세요"
                            className="w-full px-[16px] py-[14px] bg-slate-50 border border-slate-200 rounded-xl text-[16px] outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-medium placeholder:text-slate-400"
                            required
                        />
                    </div>

                    {/* 비밀번호 입력 */}
                    <div className="flex flex-col gap-[8px] mb-[8px]">
                        <label className="text-[14px] font-bold text-slate-700">비밀번호</label>
                        <div className="relative">
                            <input
                                type={showPassword ? "text" : "password"}
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                placeholder="비밀번호를 입력하세요"
                                className="w-full pl-[16px] pr-[48px] py-[14px] bg-slate-50 border border-slate-200 rounded-xl text-[16px] outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-medium placeholder:text-slate-400"
                                required
                            />
                            <Button
                                variant="ghost"
                                size="icon"
                                type="button"
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 hover:bg-transparent transition-colors h-8 w-8"
                                onClick={() => setShowPassword(!showPassword)}
                            >
                                {showPassword ? <EyeOffIcon className="w-5 h-5" /> : <EyeIcon className="w-5 h-5" />}
                            </Button>
                        </div>
                    </div>

                    {/* 비밀번호 찾기 링크 */}
                    <div className="flex justify-start mb-[32px]">
                        <Button variant="ghost" type="button" className="text-[14px] font-medium text-[#155dfc] hover:text-[#124bc9] hover:bg-transparent px-0 h-auto transition-colors">
                            비밀번호를 잊으셨나요?
                        </Button>
                    </div>

                    {/* 에러 메시지 표시 */}
                    {errorMessage && (
                        <div className="mb-[16px] text-red-500 text-sm font-medium text-center bg-red-50 p-3 rounded-lg border border-red-100">
                            {errorMessage}
                        </div>
                    )}

                    {/* 로그인 버튼 */}
                    <Button
                        type="submit"
                        disabled={isLoading}
                        className="w-full h-[52px] bg-[#155dfc] hover:bg-[#124bc9] text-white font-bold rounded-xl text-[16px] shadow-lg mb-[32px] disabled:opacity-70"
                    >
                        {isLoading ? "로그인 중..." : "로그인"}
                    </Button>

                    {/* 또는 */}
                    <div className="relative flex items-center mb-[32px]">
                        <div className="flex-grow border-t border-slate-200"></div>
                        <span className="flex-shrink-0 mx-[16px] text-slate-500 text-[14px] font-normal">또는</span>
                        <div className="flex-grow border-t border-slate-200"></div>
                    </div>

                    {/* 회원가입 섹션 */}
                    <div className="flex flex-col gap-[12px] items-center">
                        <span className="text-[16px] text-slate-600 font-normal">아직 계정이 없으신가요?</span>
                        <Link to="/signup" className="w-full">
                            <Button variant="outline" type="button" className="w-full h-[52px] bg-white border-[1.7px] border-slate-200 hover:bg-slate-50 text-slate-700 font-bold rounded-xl text-[16px] transition-colors">
                                회원가입
                            </Button>
                        </Link>
                    </div>
                </form>
            </div>
        </div>
    );
}
