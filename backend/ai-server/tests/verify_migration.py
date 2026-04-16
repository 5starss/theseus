import sys
import os
import pandas as pd
import json
import gzip

# ai-server/app 경로를 path에 추가하여 임포트 가능하게 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.quant.sources import (
    load_ohlcv_from_csv, 
    fetch_and_store_timeseries, 
    get_latest_raw_path, 
    load_raw_from_storage
)
from collector.storage import list_storage_files

def test_quant_migration():
    ticker = "005930" # 삼성전자
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../quant_agent/data_cybos"))
    
    print(f"--- [1] CSV 로드 테스트 ({ticker}) ---")
    try:
        df = load_ohlcv_from_csv(ticker, data_dir=data_dir)
        print(f"성공: {len(df)} 행 로드됨. 첫 날짜: {df['ts'].iloc[0]}")
    except Exception as e:
        print(f"실패: {e}")
        return

    print(f"\n--- [2] storage/quant 저장 테스트 ---")
    try:
        path = fetch_and_store_timeseries(ticker, data_dir=data_dir)
        print(f"성공: 파일 저장됨 -> {path}")
    except Exception as e:
        print(f"실패: {e}")
        return

    print(f"\n--- [3] 최신 파일 경로 조회 테스트 ---")
    try:
        latest = get_latest_raw_path(ticker)
        print(f"성공: 최신 경로 -> {latest}")
    except Exception as e:
        print(f"실패: {e}")
        return

    print(f"\n--- [4] 저장된 데이터 재로드 테스트 ---")
    try:
        df_reloaded = load_raw_from_storage(latest)
        print(f"성공: {len(df_reloaded)} 행 로드됨. 마지막 날짜: {df_reloaded['ts'].iloc[-1]}")
    except Exception as e:
        print(f"실패: {e}")
        return

    print(f"\n--- [5] storage 목록 조회 테스트 (Category: quant) ---")
    try:
        status = list_storage_files(category="quant", limit=5)
        print(f"성공: {status['file_count']} 개의 파일 발견.")
        for f in status['files']:
            print(f"  - {f['name']} ({f['size']} bytes)")
    except Exception as e:
        print(f"실패: {e}")
        return

    print("\n✅ 모든 퀀트 마이그레이션 인프라 테스트 통과!")

if __name__ == "__main__":
    test_quant_migration()
