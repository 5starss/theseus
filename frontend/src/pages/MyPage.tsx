import { useEffect, useState } from 'react';
import { useUserStore } from '../store/useUserStore';
import { User, Mail, TrendingUp, Check, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import type { InvestmentStyle } from '../api/user';

const STYLE_LABELS: Record<InvestmentStyle, string> = {
    BALANCED: "안정형",
    GROWTH: "성장형",
    AGGRESSIVE: "공격형"
};

const MyPage = () => {
    const { profile, fetchProfile, updateInvestmentStyle, isLoading, error } = useUserStore();
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [selectedStyle, setSelectedStyle] = useState<InvestmentStyle | null>(null);

    useEffect(() => {
        fetchProfile();
    }, [fetchProfile]);

    const handleStyleUpdate = async () => {
        if (selectedStyle) {
            await updateInvestmentStyle(selectedStyle);
            setIsDialogOpen(false);
        }
    };

    if (isLoading && !profile) {
        return (
            <div className="flex h-[80vh] w-full flex-col items-center justify-center gap-4">
                <Loader2 className="h-10 w-10 animate-spin text-blue-500" />
                <p className="text-slate-500 font-medium">내 정보를 불러오는 중입니다...</p>
            </div>
        );
    }

    if (error && !profile) {
        return (
            <div className="flex h-[80vh] w-full flex-col items-center justify-center gap-6 p-6 text-center">
                <div className="bg-red-50 p-4 rounded-full">
                    <User className="h-12 w-12 text-red-500" />
                </div>
                <div className="flex flex-col gap-2">
                    <h2 className="text-2xl font-bold text-slate-800">정보를 불러오지 못했습니다</h2>
                    <p className="text-slate-500 max-w-sm">{error}</p>
                </div>
                <Button
                    onClick={() => fetchProfile()}
                    className="bg-[#155dfc] text-white hover:bg-[#004eeb] rounded-2xl px-8 py-6 h-auto text-base font-bold shadow-lg shadow-blue-500/20"
                >
                    다시 시도하기
                </Button>
            </div>
        );
    }

    if (!profile) return null;

    return (
        <div className="flex h-full w-full flex-col bg-[#f9fafb] overflow-y-auto">
            <div className="mx-auto w-full max-w-3xl px-6 py-10 md:px-12">
                {/* Header Section */}
                <div className="mb-10 flex flex-col items-start gap-4">
                    <div className="mt-2">
                        <h1 className="text-3xl font-bold text-[#101828]">내 정보</h1>
                    </div>
                </div>

                {/* Info Cards Panel */}
                <div className="flex flex-col gap-0 overflow-hidden rounded-3xl border border-[#f3f4f6] bg-white shadow-sm">
                    {/* Nickname Row */}
                    <div className="flex items-center gap-5 border-b border-[#f3f4f6] p-8">
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eff6ff]">
                            <User className="h-6 w-6 text-[#155dfc]" />
                        </div>
                        <div className="flex flex-col gap-1">
                            <span className="text-sm font-medium text-[#6a7282]">닉네임</span>
                            <span className="text-lg font-bold text-[#101828]">{profile.nickname}</span>
                        </div>
                    </div>

                    {/* Email Row */}
                    <div className="flex items-center gap-5 border-b border-[#f3f4f6] p-8">
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#faf5ff]">
                            <Mail className="h-6 w-6 text-[#9333ea]" />
                        </div>
                        <div className="flex flex-col gap-1">
                            <span className="text-sm font-medium text-[#6a7282]">이메일</span>
                            <span className="text-lg font-bold text-[#101828]">{profile.email}</span>
                        </div>
                    </div>

                    {/* Investment Style Row */}
                    <div className="flex items-center justify-between p-8">
                        <div className="flex items-center gap-5">
                            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#f0fdf4]">
                                <TrendingUp className="h-6 w-6 text-[#16a34a]" />
                            </div>
                            <div className="flex flex-col gap-1">
                                <span className="text-sm font-medium text-[#6a7282]">투자성향</span>
                                <span className="text-lg font-bold text-[#101828]">{STYLE_LABELS[profile.investmentStyle]}</span>
                            </div>
                        </div>
                        <Button
                            variant="secondary"
                            className="bg-[#f3f4f6] text-[#364153] hover:bg-[#e5e7eb] rounded-xl px-4"
                            onClick={() => {
                                setSelectedStyle(profile.investmentStyle);
                                setIsDialogOpen(true);
                            }}
                        >
                            수정하기
                        </Button>
                    </div>
                </div>
            </div>

            {/* Investment Style Update Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent className="max-w-md rounded-3xl p-8">
                    <DialogHeader>
                        <DialogTitle className="text-2xl font-bold">투자 성향 수정</DialogTitle>
                        <DialogDescription className="text-base text-[#6a7282]">
                            변경하려는 투자 성향을 선택해 주세요.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="my-6 grid gap-3">
                        {(Object.keys(STYLE_LABELS) as InvestmentStyle[]).map((style) => (
                            <button
                                key={style}
                                onClick={() => setSelectedStyle(style)}
                                className={`flex items-center justify-between rounded-2xl border p-5 transition-all
                                    ${selectedStyle === style
                                        ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                                        : 'border-[#f3f4f6] hover:bg-gray-50'
                                    }`}
                            >
                                <span className={`text-lg font-bold ${selectedStyle === style ? 'text-blue-700' : 'text-[#101828]'}`}>
                                    {STYLE_LABELS[style]}
                                </span>
                                {selectedStyle === style && <Check className="h-5 w-5 text-blue-600" />}
                            </button>
                        ))}
                    </div>

                    <DialogFooter className="flex gap-2">
                        <Button
                            variant="outline"
                            className="flex-1 rounded-2xl py-6 text-base"
                            onClick={() => setIsDialogOpen(false)}
                        >
                            취소
                        </Button>
                        <Button
                            className="flex-1 rounded-2xl bg-[#155dfc] py-6 text-base text-white hover:bg-[#004eeb]"
                            onClick={handleStyleUpdate}
                            disabled={isLoading || !selectedStyle || selectedStyle === profile.investmentStyle}
                        >
                            {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : '저장하기'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default MyPage;
