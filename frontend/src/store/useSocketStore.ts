import { create } from 'zustand';
import { useAuthStore } from './useAuthStore';

interface SocketState {
    socket: WebSocket | null;
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    subscribe: (topic: string, ticker?: string) => void;
    unsubscribe: (topic: string, ticker?: string) => void;
}

export const useSocketStore = create<SocketState>((set, get) => ({
    socket: null,
    isConnected: false,

    connect: () => {
        if (get().socket || get().isConnected) return;

        const token = useAuthStore.getState().token;
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // 호스트 주소가 실시간 서버와 다른 경우 등 환경에 맞게 조정 필요
        const wsUrl = `${wsProtocol}//${window.location.host}/v1/stocks/ws${token ? `?token=${token}` : ''}`;

        console.log('Attempting to connect to Global WebSocket singleton...');
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('Global WebSocket connected');
            set({ socket: ws, isConnected: true });
        };

        ws.onmessage = (event) => {
            if (!event.data) return;
            // 메시지 수신 시 필요한 스토어들에게 알림 (이벤트 버스 역할)
            // 여기서는 중앙에서 파싱하여 각 스토어의 데이터 업데이트 로직을 호출할 수 있음
            // 각 스토어(useMarketStore, useStockStore)에서 이 소켓을 참조하거나 
            // 수신 핸들러를 등록하는 방식으로 개선 가능
            window.dispatchEvent(new CustomEvent('ws-message', { detail: event.data }));
        };

        ws.onclose = (e) => {
            console.log(`Global WebSocket closed (Code: ${e.code}). Reconnecting in 3s...`);
            set({ socket: null, isConnected: false });
            // 자동 재연결 로직 (선택 사항)
            setTimeout(() => get().connect(), 3000);
        };

        ws.onerror = (err) => {
            console.error('Global WebSocket error:', err);
            ws.close();
        };
    },

    disconnect: () => {
        const { socket } = get();
        if (socket) {
            console.log('Disconnecting Global WebSocket...');
            socket.close(1000, 'App termination');
            set({ socket: null, isConnected: false });
        }
    },

    subscribe: (topic, ticker) => {
        const { socket, isConnected } = get();
        if (socket && isConnected && socket.readyState === WebSocket.OPEN) {
            console.log(`Subscribing to ${topic}${ticker ? `:${ticker}` : ''}`);
            socket.send(JSON.stringify({
                action: 'SUBSCRIBE',
                topic,
                ticker
            }));
        } else {
            // 아직 연결 전이라면 연결 후 구독하도록 큐잉하거나 재시도 로직 필요
            setTimeout(() => get().subscribe(topic, ticker), 500);
        }
    },

    unsubscribe: (topic, ticker) => {
        const { socket, isConnected } = get();
        if (socket && isConnected && socket.readyState === WebSocket.OPEN) {
            console.log(`Unsubscribing from ${topic}${ticker ? `:${ticker}` : ''}`);
            socket.send(JSON.stringify({
                action: 'UNSUBSCRIBE',
                topic,
                ticker
            }));
        }
    }
}));
