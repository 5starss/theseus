import { Sparkles } from "lucide-react";

export function AISection() {
    return (
        <div className="flex flex-col h-full p-6 w-[320px] min-w-[320px]">
            <h2 className="text-lg font-bold text-slate-800 mb-6">AI 분석</h2>
            <div className="flex-1 flex flex-col items-center justify-center text-center space-y-4">
                <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center text-blue-600 animate-pulse">
                    <Sparkles className="w-8 h-8" />
                </div>
                <p className="text-slate-400 text-sm leading-relaxed">
                    AI가 종목 정보를 분석하고 있습니다.<br />잠시만 기다려 주세요.
                </p>
            </div>
        </div>
    );
}
