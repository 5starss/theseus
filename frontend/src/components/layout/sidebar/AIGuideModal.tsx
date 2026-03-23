import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

interface AIGuideModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function AIGuideModal({ isOpen, onClose }: AIGuideModalProps) {
    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl p-0 overflow-hidden border-none rounded-3xl shadow-2xl">
                <div className="bg-purple-600 px-8 py-6 text-white relative overflow-hidden">
                    <div className="absolute -right-10 -top-10 w-40 h-40 bg-white/10 rounded-full blur-3xl" />
                    <DialogHeader>
                        <DialogTitle className="text-2xl font-black mb-2 flex items-center gap-2">
                            🤖 AI 자동매매 시작하기
                        </DialogTitle>
                        <DialogDescription className="text-purple-100 font-medium text-base">
                            3분 완성 가이드: 스마트하게 투자하는 법
                        </DialogDescription>
                    </DialogHeader>
                </div>

                <ScrollArea className="max-h-[65vh] pl-6 pr-7 pt-1 pb-4">
                    <div className="space-y-10">
                        {/* 도입부 */}
                        <p className="text-slate-600 leading-relaxed font-medium">
                            복잡한 주식 시장, 이제 AI에게 맡기고 스마트하게 투자하세요!<br />
                            딱 세 가지만 설정하면 AI가 당신의 든든한 투자 파트너가 됩니다.
                        </p>

                        <div className="space-y-12">
                            {/* STEP 1 */}
                            <section className="space-y-4">
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center font-black text-sm shrink-0">1</div>
                                    <h4 className="font-bold text-slate-900 text-lg flex items-center gap-2">
                                        AI 전용 투자금 이체하기
                                    </h4>
                                </div>
                                <div className="space-y-3">
                                    <p className="text-slate-600 text-sm leading-relaxed">
                                        AI가 매매를 수행할 수 있도록 내 기본 계좌에서 <span className="font-bold text-slate-900">'AI 전용 계좌'</span>로 투자금을 보내주세요.
                                    </p>
                                    <div className="bg-blue-50 p-4 rounded-2xl border border-blue-100 flex gap-3">
                                        <p className="text-blue-700 text-xs leading-relaxed">
                                            <span className="font-bold">💡 Tip:</span> AI는 할당된 금액 범위 내에서만 정밀하게 움직이므로, 투자하고 싶은 만큼의 예산만 이체하여 안전하게 관리할 수 있습니다.
                                        </p>
                                    </div>
                                </div>
                            </section>

                            {/* STEP 2 */}
                            <section className="space-y-4">
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center font-black text-sm shrink-0">2</div>
                                    <h4 className="font-bold text-slate-900 text-lg flex items-center gap-2">
                                        관심종목 등록하기
                                    </h4>
                                </div>
                                <div className="space-y-3 text-slate-600 text-sm leading-relaxed">
                                    <p>AI는 사용자가 <span className="font-bold text-slate-900">'관심종목'</span>으로 설정한 종목들에 대해서만 분석하고 매매를 진행합니다.</p>
                                    <ul className="list-disc list-inside space-y-1.5 text-slate-500">
                                        <li>평소 눈여겨보던 종목을 미리 관심종목 리스트에 담아주세요.</li>
                                        <li>AI가 해당 종목들의 차트와 시장 흐름을 집중적으로 모니터링합니다.</li>
                                    </ul>
                                </div>
                            </section>

                            {/* STEP 3 */}
                            <section className="space-y-4">
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center font-black text-sm shrink-0">3</div>
                                    <h4 className="font-bold text-slate-900 text-lg flex items-center gap-2">
                                        AI 투자 성향 & 분석 설정
                                    </h4>
                                </div>
                                <div className="space-y-4 text-slate-600 text-sm leading-relaxed">
                                    <p>나의 투자 스타일을 AI에게 알려주세요.</p>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100">
                                            <p className="text-slate-800 text-sm font-bold mb-1">AI 투자 성향 설정</p>
                                            <p className="text-slate-500 text-xs">'단타', '장투' 중 본인의 스타일을 선택합니다.</p>
                                        </div>
                                        <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100">
                                            <p className="text-slate-800 text-sm font-bold mb-1">AI 분석 토글 (ON)</p>
                                            <p className="text-slate-500 text-xs">이 스위치를 켜는 순간, AI가 실시간 시장 흐름을 읽기 시작합니다.</p>
                                        </div>
                                    </div>
                                </div>
                            </section>
                        </div>

                        {/* 마무리 */}
                        <section className="bg-purple-50 p-6 rounded-3xl border border-purple-100 relative overflow-hidden">
                            <h4 className="font-bold text-purple-900 text-lg mb-2 flex items-center gap-2">
                                ✅ 모든 설정 완료!
                            </h4>
                            <p className="text-purple-800 text-sm leading-relaxed">
                                설정이 끝나면 AI가 분석 결과에 따라 관심종목 중에서 최적의 타이밍에 자동으로 매수와 매도를 진행합니다. 이제 실시간 차트를 계속 확인하지 않아도 AI가 쉬지 않고 시장을 관리합니다.
                            </p>
                        </section>

                        {/* 체크포인트 */}
                        <section className="">
                            <h4 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                                💡 체크포인트
                            </h4>
                            <ul className="space-y-3 px-2">
                                {[
                                    "AI 계좌에 잔고가 충분한지 확인해 주세요.",
                                    "관심종목 리스트를 업데이트하면 AI의 매매 대상도 함께 변경됩니다.",
                                    "투자 성향은 언제든 변경할 수 있으며, 변경 즉시 AI의 매매 전략에 반영됩니다."
                                ].map((text, idx) => (
                                    <li key={idx} className="flex items-start gap-3 text-slate-500 text-[13px] leading-snug">
                                        <div className="w-1 h-1 bg-slate-300 rounded-full mt-2 shrink-0" />
                                        {text}
                                    </li>
                                ))}
                            </ul>
                        </section>
                    </div>
                </ScrollArea>

                <div className="p-6 bg-slate-50 flex justify-end border-t border-slate-100">
                    <button
                        onClick={onClose}
                        className="px-5 py-3 bg-purple-600 text-white font-black rounded-2xl hover:bg-purple-700 transition-all active:scale-95 shadow-lg shadow-purple-200"
                    >
                        확인
                    </button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
