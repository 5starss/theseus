import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNotificationStore, type Notification } from '../../store/useNotificationStore';
import { X, Check } from 'lucide-react';

export function NotificationToast() {
    const notifications = useNotificationStore(state => state.notifications);
    
    if (notifications.length === 0) return null;

    return (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-3 pointer-events-none items-center">
            {notifications.map((notif) => (
                <ToastItem key={notif.id} notification={notif} />
            ))}
        </div>
    );
}

function ToastItem({ notification }: { notification: Notification }) {
    const removeNotification = useNotificationStore(state => state.removeNotification);
    const navigate = useNavigate();
    const [isVisible, setIsVisible] = useState(false);

    // 종목 코드로 종목명 찾기 (스토어에 캐싱된 이름이 있으면 사용, 아니면 티커 표시)
    const stockName = notification.stockName || notification.ticker;

    useEffect(() => {
        // 애니메이션 효과를 위해 지연 실행
        const timer = setTimeout(() => setIsVisible(true), 10);
        return () => clearTimeout(timer);
    }, []);

    const handleClose = () => {
        setIsVisible(false);
        setTimeout(() => removeNotification(notification.id), 300);
    };

    const handleViewHistory = () => {
        navigate('/account/orders');
        handleClose();
    };

    const isBuy = notification.orderType === 'BUY';
    const typeText = isBuy ? '매수' : '매도';
    
    let title = '';
    let description = '';

    switch (notification.eventType) {
        case 'ORDER':
            title = `${stockName} ${notification.matchQuantity}주 ${typeText} 신청 성공`;
            description = `주당 ${notification.matchPrice.toLocaleString()}원에 ${typeText} 신청했어요.`;
            break;
        case 'MATCHED':
            title = `${stockName} ${notification.matchQuantity}주 ${typeText} 체결`;
            description = `주당 ${notification.matchPrice.toLocaleString()}원에 ${typeText}했어요.`;
            break;
        case 'ORDER_CANCEL':
            title = `${stockName} ${notification.matchQuantity}주 ${typeText} 취소 신청 성공`;
            description = `취소 신청을 접수했어요.`;
            break;
        case 'CANCELLED':
            title = `${stockName} ${notification.matchQuantity}주 ${typeText} 취소 완료`;
            description = `주문 취소가 완료되었어요.`;
            break;
    }

    return (
        <div 
            className={`
                pointer-events-auto w-[420px] bg-[#1e293b] text-white rounded-2xl py-2.5 px-4 shadow-2xl border border-slate-700/50
                flex items-center gap-3 transition-all duration-300 transform
                ${isVisible ? 'translate-y-0 opacity-100' : '-translate-y-8 opacity-0'}
            `}
        >
            {/* Success Icon */}
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-[#10b981] flex items-center justify-center">
                <Check className="w-4 h-4 text-white stroke-[3px]" />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <h4 className="text-[14px] font-bold truncate leading-tight">
                    {title}
                </h4>
                <p className="text-[12px] text-slate-300 mt-0">
                    {description}
                </p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
                <button 
                    onClick={handleViewHistory}
                    className="whitespace-nowrap bg-slate-700/50 hover:bg-slate-700 text-[12px] font-bold px-2.5 py-1.5 rounded-md transition-colors border border-slate-600"
                >
                    내역 보기
                </button>
                <button 
                    onClick={handleClose}
                    className="p-1 text-slate-400 hover:text-white transition-colors"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
}
