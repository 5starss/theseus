import type { ReactNode } from "react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";

interface HistoryDetailModalProps {
    isOpen: boolean;
    onClose: () => void;
    children: ReactNode;
}

export function HistoryDetailModal({ isOpen, onClose, children }: HistoryDetailModalProps) {
    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="bg-white rounded-2xl shadow-xl w-full max-w-[360px] max-h-[90vh] overflow-y-auto flex flex-col p-0 border-none sm:rounded-2xl gap-0 [&>button]:hidden">
                <DialogTitle className="sr-only">상세 정보</DialogTitle>
                <DialogDescription className="sr-only">선택된 항목의 상세 내역입니다.</DialogDescription>
                {children}
            </DialogContent>
        </Dialog>
    );
}
