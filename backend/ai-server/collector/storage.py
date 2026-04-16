"""
storage.py
──────────
데이터 스냅샷을 카테고리별 하위 디렉토리에 저장·관리하는 유틸리티.

카테고리:
  - news  : KIS 뉴스·Toss 커뮤니티 스냅샷
  - quant : OHLCV 원본·피처·모델 파일
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List

_BASE_DIR = os.path.abspath(os.getenv("AI_SERVER_STORAGE_DIR", "storage"))


def get_storage_dir(category: str = "news") -> str:
    """카테고리에 해당하는 storage 하위 디렉토리 경로를 반환합니다."""
    storage_dir = os.path.join(_BASE_DIR, category)
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


def save_snapshot(
    prefix: str,
    ticker: str,
    payload: Dict[str, Any],
    category: str = "news",
) -> str:
    """JSON 스냅샷을 저장하고 파일 경로를 반환합니다."""
    storage_dir = get_storage_dir(category)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(storage_dir, f"{prefix}_{ticker}_{timestamp}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return file_path


def list_storage_files(
    category: str = "news",
    limit: int = 20,
) -> Dict[str, Any]:
    """지정된 카테고리 디렉토리의 JSON/JSON.GZ 파일 목록을 반환합니다."""
    storage_dir = get_storage_dir(category)
    names = [
        n for n in os.listdir(storage_dir) 
        if n.endswith(".json") or n.endswith(".json.gz")
    ]
    names.sort(reverse=True)

    files: List[Dict[str, Any]] = []
    for name in names[:limit]:
        path = os.path.join(storage_dir, name)
        stat = os.stat(path)
        files.append(
            {
                "name": name,
                "path": path,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )
    return {
        "storage_dir": storage_dir,
        "file_count": len(names),
        "files": files,
    }

