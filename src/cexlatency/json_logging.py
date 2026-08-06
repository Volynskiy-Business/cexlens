from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .models import utc_now


class JsonEventLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, event: str, **fields: Any) -> None:
        record = {"timestamp": utc_now(), "event": event, **fields}
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")

    def probe_error(self, run_id: str, exchange: str, endpoint: str, probe_type: str, classification: str | None, detail: str | None, retry_number: int = 0, recoverable: bool = True) -> None:
        self.emit("probe_error", run_id=run_id, exchange=exchange, endpoint=endpoint, probe_type=probe_type, exception_type=classification or "UNKNOWN_ERROR", retry_number=retry_number, classification=classification or "UNKNOWN_ERROR", recoverable=recoverable, detail=detail)
