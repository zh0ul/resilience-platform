"""Evidence collection helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from resilience_platform.settings import Settings, get_settings


def evidence_run_dir(settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    path = cfg.evidence_dir / cfg.effective_run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_failure_artifact(
    name: str,
    payload: dict[str, Any],
    settings: Settings | None = None,
) -> Path:
    out_dir = evidence_run_dir(settings)
    artifact = out_dir / f"{name}.json"
    envelope = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "payload": payload,
    }
    artifact.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return artifact
