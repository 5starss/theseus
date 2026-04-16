// 공통 API 응답 구조
export interface ApiResponse<T> {
    success: boolean;
    data: T;
    isSuccess?: boolean; // 백엔드 필드명 대응
    result?: T;         // 백엔드 필드명 대응
    message?: string;
    code?: string;
}

// 주식 관련 커스텀 이벤트 타입 정의
export interface StockWSMessageEvent extends CustomEvent<string> {
    detail: string;
}

declare global {
    interface WindowEventMap {
        'ws-message': StockWSMessageEvent;
    }
}
