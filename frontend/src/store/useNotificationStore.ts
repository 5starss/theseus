import { create } from 'zustand';
import { useAuthStore } from './useAuthStore';
import { useAccountStore } from './useAccountStore';

export interface Notification {
    id: string;
    eventType: 'MATCHED' | 'CANCELLED' | 'ORDER' | 'ORDER_CANCEL'; // 백엔드 EventType 에 맞춰 확장
    orderType: 'BUY' | 'SELL';
    ticker: string;
    stockName?: string;
    matchPrice: number;
    matchQuantity: number;
    executedAt: string;
    read: boolean;
}

interface NotificationState {
    notifications: Notification[];
    sseConnected: boolean;
    eventSource: EventSource | null;
    
    addNotification: (notification: Omit<Notification, 'id' | 'read'>) => void;
    markAsRead: (id: string) => void;
    removeNotification: (id: string) => void;
    
    connectSSE: () => void;
    disconnectSSE: () => void;
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
    notifications: [],
    sseConnected: false,
    eventSource: null,

    addNotification: (notif) => {
        const id = Math.random().toString(36).substring(2, 9);
        set((state) => ({
            notifications: [{ ...notif, id, read: false }, ...state.notifications]
        }));
        
        // 2.5초 후 자동 삭제 (토스트용)
        setTimeout(() => {
            get().removeNotification(id);
        }, 2500);
    },

    markAsRead: (id) => set((state) => ({
        notifications: state.notifications.map(n => n.id === id ? { ...n, read: true } : n)
    })),

    removeNotification: (id) => set((state) => ({
        notifications: state.notifications.filter(n => n.id !== id)
    })),

    connectSSE: () => {
        const { token, isLoggedIn } = useAuthStore.getState();
        if (!isLoggedIn || !token || get().eventSource) return;

        console.log("Connecting to SSE Notification Server...");
        
        // API Gateway를 통해 인증하기 위해 token을 쿼리 스트링으로 전달
        // VITE_API_BASE_URL이 없으면 빈 문자열을 사용하여 절대 경로(/api/...)로 시작하도록 함
        const sseUrl = `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/core/notifications/subscribe?token=${token}`;
        const es = new EventSource(sseUrl);

        es.onopen = () => {
            console.log("SSE Connection Opened");
            set({ sseConnected: true });
        };

        es.onerror = (e) => {
            console.error("SSE Connection Error", e);
            set({ sseConnected: false });
            es.close();
            set({ eventSource: null });
            
            // 재연결 로직 (선택적)
            setTimeout(() => get().connectSSE(), 5000);
        };

        // 체결 알림 수신
        es.addEventListener('order_notification', (event: MessageEvent) => {
            try {
                const data = JSON.parse(event.data);
                console.log("Received Notification:", data);
                
                get().addNotification({
                    eventType: data.eventType,
                    orderType: data.orderType,
                    ticker: data.ticker,
                    matchPrice: data.matchPrice,
                    matchQuantity: data.matchQuantity,
                    executedAt: data.executedAt,
                });

                // 체결(MATCHED) 또는 취소(CANCELLED) 알림 수신 시 관련 데이터 리프레시
                if (data.eventType === 'MATCHED' || data.eventType === 'CANCELLED') {
                    const accountStore = useAccountStore.getState();
                    
                    // 병렬로 데이터 갱신 (지연 없이 즉시 갱신)
                    Promise.all([
                        accountStore.fetchBalance(),
                        accountStore.fetchPositions(),
                        accountStore.fetchPendingOrders(),
                        accountStore.fetchCompletedOrders()
                    ]).then(() => {
                        console.log("Account data refreshed after SSE notification");
                    });
                }
            } catch (err) {
                console.error("Failed to parse SSE notification data", err);
            }
        });

        set({ eventSource: es });
    },

    disconnectSSE: () => {
        const es = get().eventSource;
        if (es) {
            es.close();
            console.log("SSE Connection Closed");
        }
        set({ eventSource: null, sseConnected: false });
    }
}));

// 테스트용 전역 노출
if (typeof window !== 'undefined') {
    (window as any).notificationStore = useNotificationStore.getState();
}
