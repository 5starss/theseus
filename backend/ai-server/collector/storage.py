import json
import os
from datetime import datetime
from typing import Any, Dict


def get_storage_dir() -> str:
    storage_dir = os.getenv("AI_SERVER_STORAGE_DIR", "storage")
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


def save_snapshot(prefix: str, ticker: str, payload: Dict[str, Any]) -> str:
    storage_dir = get_storage_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(storage_dir, f"{prefix}_{ticker}_{timestamp}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return file_path

