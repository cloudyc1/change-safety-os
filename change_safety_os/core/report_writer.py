from __future__ import annotations

from typing import Any

from change_safety_os.core.change_context import ChangeContext


class ReportWriter:
    def __init__(self, context: ChangeContext):
        self.context = context

    def update_state(self, **updates: Any) -> None:
        self.context.state.update(updates)
        self.context.save()
        self.render()

    def render(self) -> None:
        state = self.context.state
        impact = state.get("impact") or {}
        decision = state.get("decision") or {}
        lines = [
            "# Change Safety Record",
            "",
            "## Goal",
            str(state.get("goal") or ""),
            "",
            "## Evidence Before Change",
            _list_or_placeholder(state.get("evidence_before_change")),
            "",
            "## Touched Surface",
            _list_or_placeholder((impact or {}).get("files")),
            "",
            "## Impact Radius",
            f"- Risk: {(impact or {}).get('risk', 'unknown')}",
            f"- Domains: {', '.join((impact or {}).get('domains') or []) or 'none'}",
            f"- Adjacent domains: {', '.join((impact or {}).get('adjacent_domains') or []) or 'none'}",
            "",
            "## Shared Contracts",
            _list_or_placeholder((impact or {}).get("contracts")),
            "",
            "## Contract Review",
            _contract_summary(state.get("contract_reviews") or {}),
            "",
            "## Protected Field Hits",
            _protected_field_summary(state.get("protected_field_hits") or []),
            "",
            "## Caller Trace",
            _caller_summary(state.get("caller_map") or {}),
            "",
            "## Verification Plan",
            _list_or_placeholder((impact or {}).get("required_guards")),
            "",
            "## Guard Results",
            _mapping_summary(state.get("guards") or {}),
            "",
            "## Probe Results",
            _mapping_summary(state.get("probes") or {}),
            "",
            "## Unchecked Gaps",
            _list_or_placeholder(state.get("unchecked_gaps")),
            "",
            "## Decision",
            f"- Status: {decision.get('status', 'pending')}",
            f"- Reason: {decision.get('reason', '')}",
            "",
        ]
        self.context.record_path.write_text("\n".join(lines), encoding="utf-8")


def _list_or_placeholder(values: Any) -> str:
    if not values:
        return "- Not recorded."
    if isinstance(values, str):
        return f"- {values}"
    return "\n".join(f"- {item}" for item in values)


def _mapping_summary(values: dict) -> str:
    if not values:
        return "- Not run."
    lines = []
    for key in sorted(values):
        item = values[key] or {}
        lines.append(f"- {key}: {item.get('status', 'unknown')}")
    return "\n".join(lines)


def _contract_summary(values: dict) -> str:
    if not values:
        return "- Not checked."
    lines = []
    for key in sorted(values):
        item = values[key] or {}
        status = item.get("status", "unknown")
        owner = item.get("owner") or "unknown owner"
        lines.append(f"- {key}: {status} ({owner})")
        invariants = item.get("invariants") or []
        for invariant in invariants[:5]:
            lines.append(f"  - invariant: {invariant}")
    return "\n".join(lines)


def _protected_field_summary(values: list) -> str:
    if not values:
        return "- No protected fields detected."
    lines = []
    for item in values[:50]:
        lines.append(f"- {item.get('field')} at {item.get('file')}:{item.get('line')}")
    if len(values) > 50:
        lines.append(f"- ... {len(values) - 50} more hits omitted")
    return "\n".join(lines)


def _caller_summary(values: dict) -> str:
    if not values:
        return "- Not traced or no adjacent callers found."
    lines = []
    for symbol in sorted(values):
        callers = values[symbol] or []
        lines.append(f"- {symbol}: {', '.join(callers[:8])}")
        if len(callers) > 8:
            lines.append(f"  - ... {len(callers) - 8} more files omitted")
    return "\n".join(lines)
