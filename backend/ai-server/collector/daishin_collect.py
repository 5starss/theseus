import csv
import os
import sys
import time
from datetime import datetime, timedelta

import win32com.client


OUT_DIR = "data_cybos_1m"

# 여러 종목 넣으면 순서대로 반복 수집
# CYBOS는 보통 A + 6자리 종목코드 형식 사용
SYMBOLS = [
    "A005930", #"삼성전자"
    "A000660", #"SK하이닉스"
    "A373220", #"LG에너지솔루션"
    "A207940", #"삼성바이오로직스"
    "A005380", #"현대차"
    "A000270", #"기아"
    "A068270", #"셀트리온"
    "A005490", #"POSCO홀딩스"
    "A035420", #"NAVER"
    "A051910", #"LG화학"
    "A028260", #"삼성물산"
    "A012330", #"현대모비스"
    "A105560", #"KB금융"
    "A055550", #"신한지주"
    "A032830", #"삼성생명"
    "A003670", #"포스코퓨처엠"
    "A035720", #"카카오"
    "A066570", #"LG전자"
    "A323410", #"카카오뱅크"
    "A015760", #"한국전력"
    "A000810", #"삼성화재"
    "A316140", #"우리금융지주"
    "A024110", #"기업은행"
    "A011200", #"HMM"
    "A010130", #"고려아연"
    "A033780", #"KT&G"
    "A086280", #"현대글로비스"
    "A017670", #"SK텔레콤"
    "A009150", #"삼성전기"
    "A259960", #"크래프톤"
    "A034020", #"두산에너빌리티"
    "A036570", #"엔씨소프트"
    "A018260", #"삼성SDS"
    "A042700", #"한미반도체"
    "A010140", #"삼성중공업"
    "A011170", #"롯데케미칼"
    "A267250", #"HD현대"
    "A090430", #"아모레퍼시픽"
    "A003490", #"대한항공"
    "A051900", #"LG생활건강"
]

# 최근 2년 기준 시점
CUTOFF_DT = datetime.now() - timedelta(days=365 * 2)

# StockChart 1회 최대 요청 수
BATCH_COUNT = 1999


def wait_rate_limit():
    """
    CYBOS 시세 요청 제한 회피.
    남은 요청 수가 없으면 남은 시간만큼 대기.
    """
    cp_cybos = win32com.client.Dispatch("CpUtil.CpCybos")
    remain = cp_cybos.GetLimitRemainCount(1)  # 1: 시세 RQ
    if remain <= 0:
        wait_ms = cp_cybos.LimitRequestRemainTime
        wait_sec = max(wait_ms / 1000.0, 0.2)
        print(f"[RATE LIMIT] waiting {wait_sec:.2f}s")
        time.sleep(wait_sec)


def check_connection():
    """
    CYBOS Plus 연결 여부 확인.
    """
    cp_cybos = win32com.client.Dispatch("CpUtil.CpCybos")
    if cp_cybos.IsConnect == 0:
        raise RuntimeError(
            "CYBOS Plus가 연결되어 있지 않습니다. "
            "CYBOS Plus 로그인 후 다시 실행하세요."
        )


def yyyymmdd_to_str(v):
    s = str(v)
    if len(s) != 8:
        raise ValueError(f"unexpected date format: {v}")
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def hhmm_to_str(v):
    """
    CYBOS 분봉 시간은 보통 HHMM 형태.
    예: 901 -> 09:01:00, 1530 -> 15:30:00
    """
    s = str(v).zfill(4)
    return f"{s[0:2]}:{s[2:4]}:00"


def to_datetime(date_val, time_val):
    return datetime.strptime(
        f"{yyyymmdd_to_str(date_val)} {hhmm_to_str(time_val)}",
        "%Y-%m-%d %H:%M:%S"
    )


def fetch_recent_2y_1m(symbol: str):
    """
    최근 2년치 1분봉을 연속 조회로 수집.
    반환값: 오래된 것부터 정렬된 list[dict]
    """
    chart = win32com.client.Dispatch("CpSysDib.StockChart")
    rows = []
    seen = set()

    chart.SetInputValue(0, symbol)                   # 종목코드
    chart.SetInputValue(1, ord('2'))                # 개수로 조회
    chart.SetInputValue(4, BATCH_COUNT)             # 요청 개수
    chart.SetInputValue(5, [0, 1, 2, 3, 4, 5, 8])   # 날짜, 시간, 시가, 고가, 저가, 종가, 거래량
    chart.SetInputValue(6, ord('m'))                # 분 차트
    chart.SetInputValue(7, 1)                       # 1분봉
    chart.SetInputValue(9, ord('1'))                # 수정주가 사용
    chart.SetInputValue(10, ord('3'))               # 시간외 거래량 모두 제외

    request_no = 0

    while True:
        wait_rate_limit()
        request_no += 1
        chart.BlockRequest()

        status = chart.GetDibStatus()
        msg = chart.GetDibMsg1()
        if status != 0:
            raise RuntimeError(f"[{symbol}] request failed: status={status}, msg={msg}")

        count = chart.GetHeaderValue(3)
        if count == 0:
            break

        batch_oldest_dt = None

        for i in range(count):
            date_val = chart.GetDataValue(0, i)
            time_val = chart.GetDataValue(1, i)
            open_ = chart.GetDataValue(2, i)
            high = chart.GetDataValue(3, i)
            low = chart.GetDataValue(4, i)
            close = chart.GetDataValue(5, i)
            volume = chart.GetDataValue(6, i)

            dt = to_datetime(date_val, time_val)

            if batch_oldest_dt is None or dt < batch_oldest_dt:
                batch_oldest_dt = dt

            if dt < CUTOFF_DT:
                continue

            key = (symbol, dt)
            if key in seen:
                continue
            seen.add(key)

            rows.append({
                "symbol": symbol.replace("A", ""),
                "ts": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "open": int(open_),
                "high": int(high),
                "low": int(low),
                "close": int(close),
                "volume": int(volume),
            })

        print(
            f"[{symbol}] request={request_no}, "
            f"received={count}, kept={len(rows)}, continue={chart.Continue}"
        )

        if batch_oldest_dt is not None and batch_oldest_dt < CUTOFF_DT:
            break

        if not chart.Continue:
            break

    rows.sort(key=lambda x: x["ts"])
    return rows


def save_csv(symbol: str, rows):
    """
    종목별로 개별 CSV 저장.
    예: 005930_1m_2y.csv
    """
    os.makedirs(OUT_DIR, exist_ok=True)

    clean_symbol = symbol.replace("A", "")
    out_path = os.path.join(OUT_DIR, f"{clean_symbol}_1m_2y.csv")

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["symbol", "ts", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"[SAVE] {out_path} rows={len(rows)}")


def main():
    check_connection()

    total = len(SYMBOLS)
    success = 0
    failed = 0

    print(f"총 {total}개 종목 수집 시작\n")

    for idx, symbol in enumerate(SYMBOLS, start=1):
        print("=" * 70)
        print(f"[{idx}/{total}] START {symbol}")
        print("=" * 70)

        try:
            rows = fetch_recent_2y_1m(symbol)
            save_csv(symbol, rows)
            success += 1
            print(f"[DONE] {symbol}\n")
        except Exception as e:
            failed += 1
            print(f"[ERROR] {symbol}: {e}\n", file=sys.stderr)

        # 종목 간 짧은 쉬는 시간
        time.sleep(0.5)

    print("=" * 70)
    print("수집 종료")
    print(f"성공: {success}")
    print(f"실패: {failed}")
    print("=" * 70)


if __name__ == "__main__":
    main()