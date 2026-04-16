/**
 * 주식 가격에 따른 호가 단위를 계산하여 반환
 * (한국거래소 코스피/코스닥 주식 호가단위 기준)
 * 
 * - 2,000원 미만: 1원
 * - 2,000원 ~ 5,000원 미만: 5원
 * - 5,000원 ~ 20,000원 미만: 10원
 * - 20,000원 ~ 50,000원 미만: 50원
 * - 50,000원 ~ 200,000원 미만: 100원
 * - 200,000원 ~ 500,000원 미만: 500원
 * - 500,000원 이상: 1,000원
 * 
 * @param price 현재 호가 가격
 * @returns 해당 가격대에서의 호가 단위
 */
export const getTickSize = (price: number): number => {
    if (price < 2000) return 1;
    if (price < 5000) return 5;
    if (price < 20000) return 10;
    if (price < 50000) return 50;
    if (price < 200000) return 100;
    if (price < 500000) return 500;
    return 1000;
};
