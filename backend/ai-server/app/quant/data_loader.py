import logging
import os
from typing import Optional

import pandas as pd
from collector.storage import get_storage_dir
from app.shared.infra.s3_client import s3_client
from datetime import datetime
from app.trading.constants import KST

logger = logging.getLogger(__name__)


def get_latest_feature_s3_key(ticker: str) -> Optional[str]:
    """S3에서 당일 해당 종목의 가장 최신 피처 파일 키를 조회합니다."""
    today_str = datetime.now(KST).strftime("%Y%m%d")
    s3_prefix = f"features/{today_str}/{ticker}/"
    s3_files = s3_client.list_files(s3_prefix)
    if not s3_files:
        logger.warning(f"[{ticker}] S3 피처 파일이 없습니다. prefix={s3_prefix}")
        return None
    return sorted(s3_files)[-1]


def download_and_load_feature_df(ticker: str, s3_key: str) -> Optional[pd.DataFrame]:
    """S3 피처 파일을 로컬에 다운로드하고 DataFrame으로 로드합니다."""
    relative_key = s3_key
    if s3_client.path_prefix and s3_key.startswith(s3_client.path_prefix):
        relative_key = s3_key[len(s3_client.path_prefix):].lstrip("/")

    quant_storage_dir = get_storage_dir("quant")
    local_path = os.path.join(quant_storage_dir, os.path.basename(s3_key))
    if not s3_client.download_file(relative_key, local_path):
        logger.warning(f"[{ticker}] S3 피처 다운로드 실패: {relative_key}")
        return None

    try:
        feat_df = pd.read_csv(local_path, compression="gzip" if local_path.endswith(".gz") else "infer")
    except Exception as exc:
        logger.error(f"[{ticker}] S3 피처 파일 로드 실패: {exc}")
        return None

    if feat_df.empty:
        logger.warning(f"[{ticker}] S3 피처 데이터가 비어 있습니다.")
        return None

    return feat_df
