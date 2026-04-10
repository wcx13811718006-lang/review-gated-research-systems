from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def append_progress_event(path: Path, stage: str, detail: str, count: int | None = None) -> None:
    event = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "detail": detail,
    }
    if count is not None:
        event["count"] = count

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

