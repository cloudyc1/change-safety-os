from __future__ import annotations

from change_safety_os.core.change_context import ChangeContext
from change_safety_os.core.report_writer import ReportWriter


def add_evidence(context: ChangeContext, *, kind: str, text: str) -> None:
    evidence = list(context.state.get("evidence_before_change") or [])
    evidence.append({"kind": kind, "text": text})
    ReportWriter(context).update_state(evidence_before_change=evidence)
