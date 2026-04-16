/**
 * 백엔드 에러 메시지 처리 유틸리티
 */

/**
 * 에러 코드에 해당하는 메시지를 반환합니다.
 * 백엔드에서 내려준 message(fallbackMessage)가 있으면 그것을 최우선으로 사용합니다.
 */
export function getErrorMessage(code: string, fallbackMessage?: string): string {
    // 1. 백엔드에서 보내준 메시지가 있으면 그대로 사용 (가장 정확함)
    if (fallbackMessage) {
        return fallbackMessage;
    }

    // 2. 메시지가 없을 경우에만 코드를 포함하여 출력 (최소한의 방어 로직)
    return `오류가 발생했습니다. (${code})`;
}
