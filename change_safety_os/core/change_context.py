from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "change"


@dataclass
class ChangeContext:
    change_id: str
    report_dir: Path
    state: Dict[str, Any]

    @property
    def state_path(self) -> Path:
        return self.report_dir / "state.json"

    @property
    def record_path(self) -> Path:
        return self.report_dir / "change-safety-record.md"

    @classmethod
    def start(cls, *, goal: str, report_root: Path) -> "ChangeContext":
        now = datetime.now()
        change_id = f"{now.strftime('%Y%m%d-%H%M%S')}-{_slugify(goal)}"
        report_dir = report_root / change_id
        report_dir.mkdir(parents=True, exist_ok=False)
        state: Dict[str, Any] = {
            "change_id": change_id,
            "goal": goal,
            "created_at": now.isoformat(timespec="seconds"),
            "impact": None,
            "guards": {},
            "probes": {},
            "unchecked_gaps": [],
            "decision": None,
        }
        context = cls(change_id=change_id, report_dir=report_dir, state=state)
        context.save()
        context.record_path.write_text(_initial_record(state), encoding="utf-8")
        return context

    @classmethod
    def load(cls, report_dir: Path) -> "ChangeContext":
        state_path = report_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return cls(change_id=str(state["change_id"]), report_dir=report_dir, state=state)

    @classmethod
    def load_latest(cls, report_root: Path) -> "ChangeContext":
        candidates = [path for path in report_root.iterdir() if path.is_dir() and (path / "state.json").exists()]
        if not candidates:
            raise FileNotFoundError(f"No change safety reports found in {report_root}")
        return cls.load(sorted(candidates)[-1])

    def save(self) -> None:
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")


def _initial_record(state: Dict[str, Any]) -> str:
    return f"""# Change Safety Record

## Goal
{state.get("goal", "")}

## Evidence Before Change
- Not recorded yet.

## Touched Surface
- Not scanned yet.

## Impact Radius
- Not scanned yet.

## Shared Contracts
- Not scanned yet.

## Verification Plan
- Not generated yet.

## Result
- Not finalized yet.

## Decision
- Pending.
"""

