"""Append-only audit trail: output/audit_trail.json.

The file is one JSON array that only grows. Each write reads the array,
appends, writes a temp file, then os.replace()s it, so a crash can't leave
half a file. An unreadable file is moved aside (never deleted) and a new
array starts.

Entries (one per agent-loop step, plus run boundaries):

  {
    "time": "2026-11-07T13:02:11Z",        UTC
    "ticket_run_id": "a1b2c3d4",           one id for everything done on a ticket run
    "ticket_id": 101,
    "agent": "accounting",
    "agent_run_id": "e5f6a7b8",
    "parent_agent_run_id": "a1b2c3d4-boss" | null,
    "chain": ["boss", "accounting"],       who delegated to whom
    "depth": 1,
    "event": "run_start" | "model_step" | "tool_results" | "delegation"
             | "guardrail" | "run_end" | "error",
    "step": 2,                             loop iteration within this agent run
    "model": "gpt-6-luna",
    "text": "...",                         model's text (if any)
    "tool_calls": [{"tool": "get_cash_position", "args": "{}"}],
    "tool_results": [{"tool": "get_cash_position", "result": "{...}"}],
    "tokens": {"input": 1200, "output": 85},          this step
    "ticket_usage": {"requests": 7, "input_tokens": ..., "output_tokens": ...},
    "stop_reason": "tool_call" | "final_result" | "retry" | ...
  }

Long fields are cut to MAX_FIELD characters.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = Path(os.getenv("CAMPUS_AUDIT_PATH", ROOT / "output" / "audit_trail.json"))
MAX_FIELD = 600
_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short(value: Any, limit: int = MAX_FIELD) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def append(entry: dict, path: Path | None = None) -> None:
    """Append one entry. Never edits or removes earlier entries."""
    path = path or AUDIT_PATH
    entry = {"time": now(), **entry}
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        data: list = []
        if path.exists() and path.stat().st_size:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    raise ValueError("audit file is not a JSON array")
            except (ValueError, json.JSONDecodeError):
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                path.rename(path.with_name(f"audit_trail.corrupt-{stamp}.json"))
                data = []
        data.append(entry)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
